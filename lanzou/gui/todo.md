# TODO

1. 设置用户所有分享界面 提前码：
(https://lanzous.com/u/[用户名/注册手机号])

https://pc.woozooo.com/mydisk.php?item=profile
POST

data: {
    action=password
    task=codepwd
    formhash=576b5416
    codeoff=1  # 开启密码
    code='密码'
}

resp:
    text
    ```html
    <div class="info_box">
    <div align="center" style="display:none;">提示信息</div>
    <div align="center">
    <div class="info_b2"><p>恭喜您，设置成功</p>
    </div>
    ```

2. 获取使用 cookie 登录用户名：

https://pc.woozooo.com/mydisk.php?item=profile&action=mypower
GET

resp：
    ```py
    re.fandall(r'url ='https://wwa.lanzous.com/u/(\w+)?t2';', resp.text)
    ```

3. 个性域名设置：

```
type : 'post',
			url : '/doupload.php',
			data : { 'task':48,'domain':domainadd},
			dataType : 'json',
			success:function(msg){
				if(msg.zt == '1'){
```

切换为修改的域名：
```
type : 'post',
			url : '/doupload.php',
			data : { 'task':49,'type':1 },
			dataType : 'json',
			success:function(msg){
				if(msg.zt == '1'){
```

3. 配置说话：
https://pc.woozooo.com/mydisk.php?item=profile
POST

data : {
    action=password
    task=titlei
    formhash=3db10c77
    titlei='Title'  # 标题
    titlet=''  # 说话  
}

resp:

```
<div class="info_box">
<div align="center" style="display:none;">提示信息</div>
<div align="center">
<div class="info_b2"><p>恭喜您，设置成功</p>
</div>
```
