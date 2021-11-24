import re

class AristaEOS():
    def __init__(self):
        self.factName = 'arista.eos.eos_facts'

    def _getVlans(self, inLine):
        out = []
        tmpVlans = inLine.split()[-1:][0] # Get the last item from split, e.g. 1127,1779-1799,2803
        for splPorts in tmpVlans.split(','):
            splRange = splPorts.split('-')
            if len(splRange) == 2:
                for i in range(int(splRange[0]), int(splRange[1]) + 1):
                    out.append(i)
            else:
                out.append(splRange[0])
        return out

    def parser(self, ansibleOut):
        out = {}
        interfaceSt = ""
        for line in ansibleOut['event_data']['res']['ansible_facts']['ansible_net_config'].split('\n'):
            line = line.strip() # Remove all white spaces
            if line == "!" and interfaceSt:
                interfaceSt = "" # This means interface ended!
            elif line.startswith('interface'):
                interfaceSt = line[10:]
            elif interfaceSt:
                if line.startswith('switchport trunk allowed vlan') or line.startswith('switchport access vlan'):
                    for vlan in self._getVlans(line):
                        key = "Vlan%s" % vlan
                        out.setdefault(key, {})
                        out[key].setdefault('tagged', [])
                        out[key]['tagged'].append(interfaceSt)
                else:
                    m = re.match(r'channel-group ([0-9]+) .*', line)
                    if m:
                        chnMemberId = m.group(1)
                        key = "Port-Channel%s" % chnMemberId
                        out.setdefault(key, {})
                        out[key].setdefault('channel-member', [])
                        out[key]['channel-member'].append(interfaceSt)
        return out
