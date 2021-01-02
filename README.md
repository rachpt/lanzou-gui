<p align="center">
<img src="https://pc.woozooo.com/img/logo2.gif" width="200">
</p>

<h1 align="center">- 蓝奏云 GUI -</h1>

<p align="center">
<img src="https://img.shields.io/badge/support-Windows-blue?logo=Windows">
<img src="https://img.shields.io/badge/support-Linux-yellow?logo=Linux">
<img src="https://img.shields.io/badge/support-MacOS-green?logo=apple">
<br />
<img src="https://img.shields.io/github/v/release/rachpt/lanzou-gui.svg?logo=iCloud">
<img src="https://img.shields.io/github/last-commit/rachpt/lanzou-gui.svg">
<img src="https://img.shields.io/github/downloads/rachpt/lanzou-gui/total.svg">
</p>

- 本项目使用`PyQt5`实现图形界面，可以完成蓝奏云的大部分功能

- 得益于 API 的功能，~~可以间接突破单文件最大 100MB 的限制~~(已关闭)，可以上传任意后缀文件，同时增加了批量上传/下载的功能

- `Python` 依赖见[requirements.txt](https://github.com/rachpt/lanzou-gui/blob/master/requirements.txt)，[releases](https://github.com/rachpt/lanzou-gui/releases) 有打包好了的 Windows 可执行程序，但**可能不是最新的**

# 预览

![lanzou-gui_screenshot](https://i.loli.net/2020/07/24/DmRBtuAjhikGep8.png)

[![what's-new-v0.3.6.gif](https://i.loli.net/2021/01/03/UCkicu6H7QeOyMs.gif)](https://files.catbox.moe/o2b3q1.webp)


# 说明
- 默认并发上传下载任务为3，可以自行设置，单个文件还是单线程的；

- 文件可以直接拖拽到软件界面上传，也可以使用对话框选择；

- 文件夹最多**4级**，这是蓝奏云的限制；

- 文件上传后不能改名，同时最好不要创建相同名字的文件夹；

- 更多说明与详细界面预览详见 [WiKi](https://github.com/rachpt/lanzou-gui/wiki)。


# 其他

Arch Linux [AUR](https://aur.archlinux.org/packages/lanzou-gui/)，感谢 [@bruceutut](https://aur.archlinux.org/account/bruceutut) 维护。

```sh
# Arch 系 Linux 安装命令
yay -S lanzou-gui
```

python >= 3.6。

[Gitee 镜像 repo](https://gitee.com/rachpt/lanzou-gui)，[命令行版本](https://github.com/zaxtyson/LanZouCloud-CMD)。

本项目的目的旨在学习 `PyQt5` 在开发桌面程序方面的应用，如需进行其他目的使用，请遵照许可协议 Fork，使用本软件所造成的一切后果与本人无关。

# 致谢

[zaxtyson/LanZouCloud-API](https://github.com/zaxtyson/LanZouCloud-API)


# Licenses

lanzou-gui: Copyright (c) [rachpt](https://gitee.com/rachpt/). See the [MIT LICENSE](https://github.com/rachpt/lanzou-gui/blob/master/LICENSE) for details.

lanzou-api: Copyright (c) [zaxtyson](https://github.com/zaxtyson/). [MIT LICENSE](https://github.com/zaxtyson/LanZouCloud-API/blob/master/LICENSE).
