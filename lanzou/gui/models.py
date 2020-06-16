from collections import namedtuple

# PyQt5 信号传递数据
DlJob = namedtuple('DlJob', ['name', 'url', 'pwd', 'path', 'info', 'run', 'rate'],
                   defaults=('', '', '', '', None, False, 0))
UpJob = namedtuple('UpJob', ['furl', 'id', 'folder', 'info', 'run', 'rate', 'set_pwd', 'pwd', 'set_desc', 'desc'],
                   defaults=('', -1, '', None, False, 0, False, '', False, ''))

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
