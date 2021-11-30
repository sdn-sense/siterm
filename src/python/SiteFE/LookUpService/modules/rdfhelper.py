from rdflib import URIRef, Literal

class RDFHelper():
    """This generates all known default prefixes."""
    # pylint: disable=E1101,W0201

    def getSavedPrefixes(self):
        """Get Saved prefixes from a configuration file."""
        prefixes = {}
        for key in ['mrs', 'nml', 'owl', 'rdf', 'xml', 'xsd', 'rdfs', 'schema', 'sd']:
            prefixes[key] = self.config.get('prefixes', key)
        prefixSite = "%s:%s:%s" % (self.config.get('prefixes', 'site'),
                                   self.config.get(self.sitename, 'domain'),
                                   self.config.get(self.sitename, 'year'))
        prefixes['site'] = prefixSite
        self.prefixes = prefixes

    def genUriRef(self, prefix=None, add=None, custom=None):
        """Generate URIRef and return."""
        if custom:
            return URIRef(custom)
        if not add:
            return URIRef("%s" % self.prefixes[prefix])
        return URIRef("%s%s" % (self.prefixes[prefix], add))

    @staticmethod
    def genLiteral(value):
        """Returns simple Literal RDF out."""
        return Literal(value)

    def generateHostIsalias(self, **kwargs):
        """Generate Host Alias from configuration."""
        if 'isAlias' in kwargs['portSwitch'] and \
           kwargs['portSwitch']['isAlias']:
            self.newGraph.add((self.genUriRef('site', kwargs['newuri']),
                               self.genUriRef('nml', 'isAlias'),
                               self.genUriRef('', custom=kwargs['portSwitch']['isAlias'])))
        elif 'hostname' in kwargs['portSwitch'] and kwargs['portSwitch']['hostname'] in list(self.hosts.keys()):
            for item in self.hosts[kwargs['portSwitch']['hostname']]:
                if item['switchName'] == kwargs['switchName'] and item['switchPort'] == kwargs['portName']:
                    suri = "%s:%s" % (kwargs['newuri'], item['intfKey'])
                    self.newGraph.add((self.genUriRef('site', kwargs['newuri']),
                                       self.genUriRef('nml', 'isAlias'),
                                       self.genUriRef('site', suri)))

    def addToGraph(self, sub, pred, obj):
        """Add to graph new info.

        Input:
        sub (list) max len 2
        pred (list) max len 2
        obj (list) max len 2 if 1 will use Literal value
        """
        if len(obj) == 1 and len(sub) == 1:
            self.newGraph.add((self.genUriRef(sub[0]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genLiteral(obj[0])))
        elif len(obj) == 1 and len(sub) == 2:
            self.newGraph.add((self.genUriRef(sub[0], sub[1]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genLiteral(obj[0])))
        elif len(obj) == 2 and len(sub) == 1:
            self.newGraph.add((self.genUriRef(sub[0]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genUriRef(obj[0], obj[1])))
        elif len(obj) == 2 and len(sub) == 2:
            self.newGraph.add((self.genUriRef(sub[0], sub[1]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genUriRef(obj[0], obj[1])))
        else:
            raise Exception('Failing to add object to graph due to mismatch')
