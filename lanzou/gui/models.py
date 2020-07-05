"""
容器类，用于储存 上传、下载 任务，文件、文件夹信息
"""


class Job():
    def __init__(self, url, tp):
        self._url = url
        self._type = tp
        self._info = None
        self._run = False
        self._rate = 0

    @property
    def url(self):
        return self._url

    @property
    def info(self):
        return self._info

    @info.setter
    def info(self, info):
        self._info = info

    @property
    def run(self):
        return self._run

    @run.setter
    def run(self, run):
        self._run = run

    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, rate):
        self._rate = rate

    @property
    def type(self):
        return self._type


class DlJob(Job):
    def __init__(self, name, url, pwd, path):
        super(DlJob, self).__init__(url, 'dl')
        self._name = name
        self._pwd = pwd
        self._path = path
        self._pause = False
        self._added = False

    @property
    def name(self):
        return self._name

    @property
    def pwd(self):
        return self._pwd

    @property
    def path(self):
        return self._path

    @property
    def pause(self):
        return self._pause

    @pause.setter
    def pause(self, pause):
        self._pause = pause

    @property
    def added(self):
        return self._added

    @added.setter
    def added(self, added):
        self._added = added


class UpJob(Job):
    def __init__(self, url, fid, folder, pwd=None, desc=None):
        super(UpJob, self).__init__(url, 'up')
        self._fid = fid
        self._folder = folder
        self._pwd = pwd
        self._desc = desc

    @property
    def fid(self):
        return self._fid

    @property
    def folder(self):
        return self._folder

    @property
    def pwd(self):
        return self._pwd

    @property
    def desc(self):
        return self._desc


class Tasks(object):
    def __init__(self):
        self._items = {}
        self._dones = {}
        self._all = {}

    def __len__(self):
        return len(self._all)

    def __getitem__(self, index):
        return self._all[index]

    def __iter__(self):
        return iter(self._items)

    def update(self, tasks):
        """更新元素"""
        for key, value in tasks.items():
            if value.rate >= 1000:
                self._dones.update({key: value})
                if key in self._items:
                    del self._items[key]
            else:
                self._items.update({key: value})
                if key in self._dones:
                    del self._dones[key]
        self._all = {**self._items, **self._dones}

    def items(self):
        return self._all.items()

    def values(self):
        return self._all.values()

    def clear(self):
        """清空元素"""
        self._dones.clear()


class Infos:
    def __init__(self, name='', is_file=True, fid='', time='', size='', downs=0, desc='', pwd='', url='', durl=''):
        self._name = name
        self._is_file = is_file
        self._fid = fid
        self._time = time
        self._size = size
        self._downs = downs
        self._desc = desc
        self._pwd = pwd
        self._url = url
        self._durl = durl
        self._has_pwd = False
        self._new_pwd = ''
        self._new_des = ''
        self._new_name = ''
        self._new_fid = ''

    @property
    def name(self):
        return self._name

    @property
    def is_file(self):
        return self._is_file

    @is_file.setter
    def is_file(self, is_file):
        self._is_file = is_file

    @property
    def id(self):
        return self._fid

    @property
    def size(self):
        return self._size

    @property
    def time(self):
        return self._time

    @property
    def downs(self):
        return self._downs

    @property
    def desc(self):
        return self._desc

    @desc.setter
    def desc(self, desc):
        self._desc = desc

    @property
    def pwd(self):
        return self._pwd

    @pwd.setter
    def pwd(self, pwd):
        self._pwd = pwd

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        self._url = url

    @property
    def durl(self):
        return self._durl

    @durl.setter
    def durl(self, durl):
        self._durl = durl

    @property
    def has_pwd(self):
        return self._has_pwd

    @property
    def new_pwd(self):
        return self._new_pwd

    @new_pwd.setter
    def new_pwd(self, new_pwd):
        self._new_pwd = new_pwd

    @property
    def new_des(self):
        return self._new_des

    @new_des.setter
    def new_des(self, new_des):
        self._new_des = new_des

    @property
    def new_name(self):
        return self._new_name

    @new_name.setter
    def new_name(self, new_name):
        self._new_name = new_name

    @property
    def new_id(self):
        return self._new_fid

    @new_id.setter
    def new_id(self, new_id):
        self._new_fid = new_id


class FileInfos(Infos):
    def __init__(self, file):
        super(FileInfos, self).__init__(is_file=True)
        self._name = file.name
        self._fid = file.id
        self._time = file.time
        self._size = file.size
        self._downs = file.downs
        self._has_pwd = file.has_pwd
        self._has_des = file.has_des

    @property
    def has_des(self):
        return self._has_des


class FolderInfos(Infos):
    def __init__(self, folder):
        super(FolderInfos, self).__init__(is_file=False)
        self._name = folder.name
        self._fid = folder.id
        self._desc = folder.desc
        self._has_pwd = folder.has_pwd


class ShareFileInfos(Infos):
    def __init__(self, file):
        super(ShareFileInfos, self).__init__(is_file=True)
        self._name = file.name
        self._time = file.time
        self._size = file.size
        self._url = file.url
        self._pwd = file.pwd
