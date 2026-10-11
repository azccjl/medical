# 小车与 Ubuntu 持续校时

日期：2026-10-11，北京时间。本轮针对扫描来自未来、重复临时校准的问题，不放宽扫描或停车门限。

## 原因

两台 Ubuntu 的 `systemd-timesyncd` 虽为 active，但 `System clock synchronized: no`。配置只有默认外网时间源，小车热点内没有可用的同步结果。VMware 周期校时关闭；小车 `RTC time: n/a`。一次手动校准不能补偿后续两机走时差，也不能解决小车重启后日期回退。

这说明时间源缺失和持续纠偏缺失；尚不能把全部漂移归因于 VMware。网页因限时底盘程序结束而显示“定位过期”，是另一种情况，校时不能产生缺失的 odom/TF。

## 配置

- Ubuntu VM：`192.168.12.71`，chrony 3.2，局域网时间源，local stratum 8。只允许 `192.168.12.1` 查询 NTP。
- 小车：`192.168.12.1`，chrony 3.2，只向 VM 同步，1–4 秒查询。没有机器人→VM 的反向同步，避免循环。
- 两端停用原 `systemd-timesyncd`，chrony 开机启用，并等待网络、失败自动重试。
- ROS 运行期间只平滑调整时钟，没有 `makestep`；偏差超过 0.5 秒时 chrony 退出，不直接跳改时间。
- 小车启动检查：存在 ROS 进程或底盘串口占用时跳过初始跳时；两者都没有时，才调用标准 `chronyd -q` 做启动校准。该服务不会启动 ROS 或底盘。
- chrony 监测接口仅在 localhost；普通用户可运行 `chronyc tracking/sources`，没有开放网络远程管理。
- 旧配置备份：两台机器 `/var/backups/medical-clock-sync-20261011/`。未删除地图、JSON、lock、录包和日志。

这是离线两机时间一致性方案，并非联网 UTC 授时。当前使用 VM 日期。VM IP 必须仍为 `192.168.12.71`；若换网卡、IP 改变或恢复虚拟机快照，先重新核对时间与 ROS 状态。不要运行旧手动 date/clock_settime 校准脚本与 chrony 竞争。

## 已部署位置

- VM：`/home/ncut/medical_clock_sync_20261011/`。
- 小车：`/home/EPRobot/medical_clock_sync_20261011/`。
- 两端配置：`/etc/chrony/chrony.conf`。
- 小车启动配置：`/etc/chrony/medical-boot.conf`、`/usr/local/sbin/medical_clock_boot_guard.py`。
- 系统服务附加配置：`/etc/systemd/system/chrony.service.d/`。

部署通过 Windows vmrun → VMware Ubuntu → 固定主机密钥的 SSH 完成，没有 Windows 直接连接车端。软件包来自 Ubuntu 官方仓库；amd64/arm64 SHA256 已与元数据核对。

## 日常离线检查（不发车）

在 **VMware Ubuntu 终端**：

```bash
set -e
export PYTHONIOENCODING=utf-8
date -u -Ins
systemctl is-active chrony
chronyc tracking
chronyc -n sources -v
python2 /home/ncut/vm_connection_check_20261009.py 'date -u -Ins; systemctl is-active chrony; chronyc tracking; chronyc -n sources -v'
source /opt/ros/melodic/setup.bash
export ROS_MASTER_URI=http://192.168.12.1:11311
export ROS_IP=192.168.12.71
unset ROS_HOSTNAME
python2 - <<'PY'
from __future__ import print_function
import rospy
from sensor_msgs.msg import LaserScan
rospy.init_node('medical_daily_clock_readonly',anonymous=True)
assert not rospy.get_param('/use_sim_time',False)
for unused in range(10):
    m=rospy.wait_for_message('/medical_slam_scan',LaserScan,timeout=5)
    age=(rospy.Time.now()-m.header.stamp).to_sec()
    print('SCAN_AGE_SECONDS',age)
    assert -.02<=age<=.30,('CLOCK_OR_SCAN_FRESHNESS_REFUSED',age)
print('DAILY_SCAN_CLOCK_CHECK_PASSED_NO_MOTION')
PY
```

预期：两端 chrony 为 active；小车 tracking 的参考地址为 `192.168.12.71`，Leap status 为 Normal，sources 为 `^*`。VM 的 local stratum 为 8，因此没有外网 sources 是正常的。扫描 age 保持原 `[-0.02,0.30]` 秒门限。雷达未启动时会超时，不能误报成校时通过。

## 重启后恢复

先开 VM 并连上热点，确认 IP，再开小车。ROS/底盘尚未启动时，小车 chrony 可自动初始校准；网络晚到会重试。先执行上述只读检查，再启动 ROS 与底盘阶段。

若已有 ROS 而日期相差很大，不执行 `date -s`、`chronyc makestep` 或旧手动校准。先保持底盘停止，核对并停止相关 ROS 进程，再在**小车 Ubuntu SSH 终端**执行：

```bash
sudo systemctl restart chrony
systemctl is-active chrony
chronyc tracking
chronyc -n sources -v
```

预期：日志显示 `BOOT_CLOCK_INITIALIZATION_WITH_NO_ROS_NO_SERIAL`，随后 chrony 同步 VM。若有 ROS/串口，初始跳时会跳过；不能拿这次重启当作大偏差已修复。

## 从离线包安装（只用于尚未部署的机器）

已经部署的本机不要重复安装。安装器拒绝覆盖备份和车端阶段目录。包包含两种架构的 deb、配置、脚本、包元数据与 SHA 清单。

将包复制到 VM `/home/ncut/medical-clock-sync-offline-20261011.zip`，在 **VMware Ubuntu 终端**：

```bash
set -e
test ! -e /home/ncut/medical_clock_sync_20261011
python2 - <<'PY'
import zipfile,json,hashlib,os
d='/home/ncut/medical_clock_sync_20261011'
os.mkdir(d,0700)
with zipfile.ZipFile('/home/ncut/medical-clock-sync-offline-20261011.zip') as z:z.extractall(d)
m=json.load(open(d+'/manifest.json'))
for name,sha in m['files'].items():
    assert hashlib.sha256(open(d+'/'+name,'rb').read()).hexdigest()==sha,name
print('OFFLINE_CLOCK_MANIFEST_OK')
PY
read -rsp 'Ubuntu sudo password: ' task_clock_password
echo
python2 /home/ncut/medical_clock_sync_20261011/vm_install_medical_clock_20261011.py "$task_clock_password"
unset task_clock_password
```

前提：已有授权 SSH helper 和正确的固定主机密钥文件，VM IP 为 .71，小车底盘关闭；helper 的只读预检查脚本 `/home/ncut/robot_field_static_preflight_20261011.sh` 可用。预期安装两端 chrony，不开启底盘。凭据不写入仓库或日志。

## 验证与下一断点

进行了两轮 180 秒只读观测，使用独立 UDP 四时间戳估计两机时差，同时统计 `/medical_slam_scan` 新鲜度。

| 结果 | 第一轮 | 与导航控制门相同订阅方式的第二轮 |
|---|---:|---:|
| 后 120 秒最大绝对时差 | 1.079 ms | 0.493 ms |
| 后 120 秒时差采样数 | 60 | 60 |
| 后 120 秒雷达帧数 | 1,213 | 1,208 |
| 雷达 age 范围 | 0.112–0.303 s | 0.112–0.214 s |
| 时间采样错误 | 0 | 0 |
| 全部扫描满足原门限 | 否，1 帧超 0.30 s | 是 |

第一轮原始 JSON 的 `REFUSED` 保留，因为一帧数据 age=0.30262674 s。时差本身已在 1.1 ms 内，不能把这帧传输延迟解释成时钟漂移。第二轮观测改为与现有导航门完全相同的 `queue_size=1,tcp_nodelay=True`；未修改雷达时间戳、控制程序或扫描门限。结果为 `CONTINUOUS_CLOCK_AND_SCAN_FRESHNESS_VERIFIED`。

第二轮结束后复查原底盘、StopWindow 和静止候选 SHA，串口无人占用，无控制或 odom 发布者。随后才进入有限时零速定位。

当前验证覆盖本次会话中持续同步和新鲜度，不包含重启/断网恢复的现场验证；启动校时与自动重试已配置，但本轮没有为测试而重启小车或虚拟机。

### 静止定位续接结果

持续校时通过后执行一次 120 秒零速定位。`REINITIALIZED_NO_MOTION`，AMCL 12 条；抓取时后轴约 `x=-0.22114 m,y=-0.11103 m,yaw=0.02247 rad`。用户明确确认：轮子和车体没动、无异常，网页位置与朝向一致。

定位抓取的初始和最终严格停车窗口都通过。但硬件程序继续观测到 120 秒截止时，当前停车窗口未就绪，退出码 1，错误标签为 `STRICT_STATIONARY_WINDOW_NEVER_READY`。这个标签不能解释成全程从未通过：审计中有 READY 记录和 7 次窗口重置，失败发生在截止时当前窗口不足。整轮硬件验收保留 `REVIEW_REQUIRED`。

串口重放：7,093 个发送帧均符合零速/查询策略，5,992 个里程计帧的原始线速度全部为 0，解析拒绝和溢出均为 0；原始角速度最大绝对值 0.013439 rad/s，偶发超过严格停车门限 0.002 rad/s。用户的肉眼静止观察不能替代该软件窗口证据，因此没有放宽门限，没有生成可发车验收文件。

定位抓取期间有一条 `/initialpose` 入站连接警告；AMCL 随后收到本次初始位姿，重定位结果与抓取窗口通过。警告和完整日志保留，没有把它作为已排除的问题。

最后复查：两端 chrony active/enabled，原 timesyncd inactive；机器人串口无占用，无 odom/控制发布者，8083 导航禁用且没有任务，8082 没有运行。限时底盘已退出，所以稍后网页 odom/TF 会过期；这是数据源结束，不是持续校时失效。

**下一断点：先只读分析停车窗口最后被角速度打断的原始片段，再决定最小修补和针对性验证。尚未运行地面短路线或绕场，不需要现在再搬车或开动。**

完整静止阶段命令（只用于本轮已执行步骤的说明，**不要原名重跑**）：在 VMware Ubuntu 终端，先 `bash /home/ncut/vm_field_static_preflight_20261011.sh`；通过后执行 `bash /home/ncut/vm_field_static_run1_20261011.sh`。前者预期 `FIELD_STATIC_PREFLIGHT_PASSED_NO_HARDWARE_STARTED`；后者会启动零速底盘，写新的 audit/capture，120 秒到期关闭串口。本轮后者如上述记录退出 1，不可写成通过。下次必须使用独立的新证据文件名，并提前通知现场观察。

下载及证据：Windows `D:/BaiduNetdiskDownload/F1/medical-navigation-field-static-20261011/`。只读观测会生成新的 JSON 和 lock；已生成的证据不覆盖、不删除。

离线包：同目录 `medical-clock-sync-offline-20261011.zip`。仓库证据副本：`docs/evidence/clock-sync-field-static-20261011/`。

## 回退（本轮没有执行）

先核对并停止 ROS 与底盘；分别在两端 Ubuntu 执行离线包中的：

```bash
sudo bash /路径/rollback_medical_clock_20261011.sh
```

脚本在 ROS 或底盘串口仍活跃时拒绝；符合条件后停用 chrony，恢复备份的 timesyncd 配置和原启用/运行状态，保留备份。回退会恢复此前缺少可用外网时间源的状况，不是本轮推荐操作。
