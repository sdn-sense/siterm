import copy
import pprint
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import writeActiveDeltas
from SiteRMLibs.MainUtilities import getActiveDeltas
from SiteRMLibs.MainUtilities import evaldict


dbI = getVal(getDBConn('List'), **{'sitename': 'T3_US_Caltech_Dev'})
hosts = dbI.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)
for host in hosts:
    tmpH = evaldict(host.get('hostinfo', {}))
    tmpInf = tmpH.get('Summary', {}).get('config', {}).get('qos', {}).get('interfaces', {})
    print(tmpInf)
    if not tmpInf:
        continue
    for _intf, intfDict in tmpInf.items():
        maxThrg = tmpH.get('Summary', {}).get('config', {}).get(intfDict['master_intf'], {}).get('intf_max', None)
        print(maxThrg)
        if maxThrg:
            for ipkey in ['ipv4', 'ipv6']:
                tmpIP = intfDict.get(f'{ipkey}_range', None)
                import pdb; pdb.set_trace()
                if isinstance(tmpIP, list):
                    for ipaddr in tmpIP:

                if tmpIP:
                    print(tmpIP, maxThrg)
