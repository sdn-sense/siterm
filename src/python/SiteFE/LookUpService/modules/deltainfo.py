from rdflib import Graph
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow

class DeltaInfo():
    # pylint: disable=E1101,W0201,E0203
    def _deltaReduction(self, delta, mainGraphName):
        """Delta reduction."""
        delta['content'] = evaldict(delta['content'])
        self.logger.info('Working on %s delta reduction in state' % delta['uid'])
        mainGraph = Graph()
        mainGraph.parse(mainGraphName, format='turtle')
        reduction = delta['content']['reduction']
        #tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        #tmpFile.write(reduction)
        #tmpFile.close()
        tmpGraph = Graph()
        #tmpGraph.parse(tmpFile.name, format='turtle')
        tmpGraph.parse(reduction, format='turtle')
        #os.unlink(tmpFile.name)
        self.logger.info('Main Graph len: %s Reduction Len: %s', len(mainGraph), len(tmpGraph))
        mainGraph -= tmpGraph
        self.dbI.update('deltasmod', [{'uid': delta['uid'], 'updatedate': getUTCnow(), 'modadd': 'removed'}])
        return mainGraph

    def _addDeltaStatesInModel(self, mainGraph, state, addition):
        """Add Delta States into Model."""
        # Issue details: https://github.com/sdn-sense/siterm/issues/73
        for conn in addition:
            if 'timestart' in list(conn.keys()) and state == 'committed':
                if conn['timestart'] < getUTCnow():
                    state = 'activating'
                else:
                    state = 'scheduled'
            elif 'timeend' in list(conn.keys()) and conn['timeend'] < getUTCnow() and state == 'activated':
                state = 'deactivating'
            # Add new State under SwitchSubnet
            mainGraph.add((self.genUriRef(custom=conn['connectionID']),
                           self.genUriRef('mrs', 'tag'),
                           self.genLiteral('monitor:status:%s' % state)))
            # If timed delta, add State under lifetime resource
            if 'timestart' in list(conn.keys()) or 'timeend' in list(conn.keys()):
                mainGraph.add((self.genUriRef(custom="%s:lifetime" % conn['connectionID']),
                               self.genUriRef('mrs', 'tag'),
                               self.genLiteral('monitor:status:%s' % state)))
        return mainGraph


    def _deltaAddition(self, delta, mainGraphName, updateState=True):
        """Delta addition lookup."""
        delta['content'] = evaldict(delta['content'])
        self.logger.info('Working on %s delta addition in state' % delta['uid'])
        mainGraph = Graph()
        mainGraph.parse(mainGraphName, format='turtle')
        addition = delta['content']['addition']
        #tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        #tmpFile.write(addition)
        #tmpFile.close()
        tmpGraph = Graph()
        tmpGraph.parse(addition, format='turtle')
        #os.unlink(tmpFile.name)
        self.logger.info('Main Graph len: %s Addition Len: %s', len(mainGraph), len(tmpGraph))
        mainGraph += tmpGraph
        # Add delta states for that specific delta
        mainGraph = self._addDeltaStatesInModel(mainGraph, delta['state'], evaldict(delta['addition']))
        if updateState:
            self.dbI.update('deltasmod', [{'uid': delta['uid'], 'updatedate': getUTCnow(), 'modadd': 'added'}])
        return mainGraph

    def appendDeltas(self, mainGraphName):
        """Append all deltas to Model."""
        for modstate in ['added', 'add', 'remove']:
            for delta in self.dbI.get('deltas', search=[['modadd', modstate]], limit=10):
                writeFile = False
                if delta['deltat'] == 'reduction':
                    if delta['state'] == 'failed':
                        continue
                    mainGraph = self._deltaReduction(delta, mainGraphName)
                    writeFile = True
                elif delta['deltat'] in ['addition', 'modify'] and \
                (delta['modadd'] in ['add'] or delta['state'] in ['activated', 'activating', 'committed']):
                    mainGraph = self._deltaAddition(delta, mainGraphName)
                    writeFile = True
                if writeFile:
                    with open(mainGraphName, "w", encoding='utf-8') as fd:
                        fd.write(mainGraph.serialize(format='turtle'))
