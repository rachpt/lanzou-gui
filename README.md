<p align="center">
<img src="https://pc.woozooo.com/img/logo2.gif" width="200">
</p>

<h1 align="center">- 蓝奏云 GUI -</h1>

<p align="center">
<img src="https://img.shields.io/badge/version-0.0.5-blue?logo=iCloud">
<img src="https://img.shields.io/badge/support-Windows-blue?logo=Windows">
<img src="https://img.shields.io/badge/support-Linux-yellow?logo=Linux">
<img src="https://img.shields.io/badge/support-MacOS-green?logo=apple">
</p>

- 本项目使用`PyQt5`实现图形界面，可以完成蓝奏云的大部分功能

- 得益于 API 的功能，可以间接突破单文件最大 100MB 的限制，同时增加了批量上传/下载的功能

- `Python` 依赖见[requirements.txt](https://github.com/rachpt/lanzou-gui/blob/master/requirements.txt)，[releases](https://github.com/rachpt/lanzou-gui/releases) 有打包好了的 Windows 可执行程序，但**可能不是最新的**


# 一些说明
- 目前并发下载任务为3，多个文件时最多同时3个下载，单个文件还是单线程的，后期会开放设置；

- 上传功能还不是很完善，~~不能后台上传，也就是只有所有文件上传完成后，你才能继续其他的事情~~，`v0.0.4`已经解决；

- 理想的文件上传功能是直接拖拽文件到软件界面，然而目前还不能（欢迎熟悉PyQt5的同学PR）；

- 回收站在计划中，目前还没有；

- 文件夹最多4级，这是蓝奏云的限制；

- 文件上传后不能改名，同时最好不要创建相同名字的文件夹；

- 更多说明与界面预览详见[WiKi](https://github.com/rachpt/lanzou-gui/wiki)。

## 命令行版本

[zaxtyson/LanZouCloud-CMD](https://github.com/zaxtyson/LanZouCloud-CMD)


# 其他

[Gitee 镜像repo](https://gitee.com/rachpt/lanzou-gui)

# 致谢

[zaxtyson/LanZouCloud-API](https://github.com/zaxtyson/LanZouCloud-API)
