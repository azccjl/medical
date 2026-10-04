# 智慧医运机器人

本仓库用于 EPRobot V2 智慧医运机器人比赛项目。

## 开发顺序

1. 确认 Ubuntu 虚拟机与小车的 SSH、ROS 双向通信。
2. 确认底盘、雷达、相机和语音节点正常。
3. 识别识别板一二维码，并校验干扰样本。
4. 将样本信息转换为取样窗口、化验窗口和任务队列。
5. 使用 `move_base` 完成取样、通行、避障和送样。
6. 接入语音播报、MD5 记录和比赛状态上报。

## 当前里程碑

先运行 `medical_status`，只读取 ROS 图信息并输出关键话题是否存在。确认通信稳定后，再加入运动控制。

## 运行方式

在 Ubuntu 18.04 的 ROS 工作空间中，将本仓库放到 `src` 下后编译：

```bash
catkin_make
source devel/setup.bash
rosrun medical_robot medical_status
```
