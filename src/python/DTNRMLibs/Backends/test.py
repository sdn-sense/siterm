
class RAW():
    def __init__(self, name):
        print('RAW')
        self.name = name

    def call(self):
        print('RAW %s' % self.name)

    def raw(self):
        print('Only in RAW %s' % self.name)

class Ansible():
    def __init__(self, name):
        print('ANSIBLE')
        self.name = name

    def call(self):
        print('Ansible %s' % self.name)

    def ansible(self):
        print('Only in Ansible %s' % self.name)


class Main(Ansible, RAW):
    def __init__(self, name):
        self.mainname = name
        if name == 'ansible':
            Ansible.__init__(self, name)
        elif name == 'raw':
            RAW.__init__(self, name)
        print('No Load')

import pdb; pdb.set_trace()
mm = Main('ansible')
mm.call()


