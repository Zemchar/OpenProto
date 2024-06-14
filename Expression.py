class Expression():
    filename = ""
    filetype = ""
    refreshrate = -1

    def __init__(self, filename, filetype=None, refreshrate=-1):
        self.filename = filename
        if(filetype is None):
            self.filetype = filename.split('.')[-1]
        else:
            self.filetype = filetype
        self.refreshrate = int(refreshrate)
