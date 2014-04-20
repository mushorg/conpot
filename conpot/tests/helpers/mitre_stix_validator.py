# Copyright (c) 2014, The MITRE Corporation. All rights reserved.
# See LICENSE.txt for complete terms.

import os
import re
from collections import defaultdict
from StringIO import StringIO
from lxml import etree
from lxml import isoschematron
import xlrd

class XmlValidator(object):
    NS_XML_SCHEMA_INSTANCE = "http://www.w3.org/2001/XMLSchema-instance"
    NS_XML_SCHEMA = "http://www.w3.org/2001/XMLSchema"
    
    def __init__(self, schema_dir=None, use_schemaloc=False):
        self.__imports = self._build_imports(schema_dir)
        self.__use_schemaloc = use_schemaloc
    
    def _get_target_ns(self, fp):
        '''Returns the target namespace for a schema file
        
        Keyword Arguments
        fp - the path to the schema file
        '''
        tree = etree.parse(fp)
        root = tree.getroot()
        return root.attrib['targetNamespace'] # throw an error if it doesn't exist...we can't validate
        
    def _get_include_base_schema(self, list_schemas):
        '''Returns the root schema which defines a namespace.
        
        Certain schemas, such as OASIS CIQ use xs:include statements in their schemas, where two schemas
        define a namespace (e.g., XAL.xsd and XAL-types.xsd). This makes validation difficult, when we
        must refer to one schema for a given namespace.
        
        To fix this, we attempt to find the root schema which includes the others. We do this by seeing
        if a schema has an xs:include element, and if it does we assume that it is the parent. This is
        totally wrong and needs to be fixed. Ideally this would build a tree of includes and return the
        root node.
        
        Keyword Arguments:
        list_schemas - a list of schema file paths that all belong to the same namespace
        '''
        parent_schema = None
        tag_include = "{%s}include" % (self.NS_XML_SCHEMA)
        
        for fn in list_schemas:
            tree = etree.parse(fn)
            root = tree.getroot()
            includes = root.findall(tag_include)
            
            if len(includes) > 0: # this is a hack that assumes if the schema includes others, it is the base schema for the namespace
                return fn
                
        return parent_schema
    
    def _build_imports(self, schema_dir):
        '''Given a directory of schemas, this builds a dictionary of schemas that need to be imported
        under a wrapper schema in order to enable validation. This returns a dictionary of the form
        {namespace : path to schema}.
        
        Keyword Arguments
        schema_dir - a directory of schema files
        '''
        if not schema_dir:
            return None
        
        imports = defaultdict(list)
        for top, dirs, files in os.walk(schema_dir):
            for f in files:
                if f.endswith('.xsd'):
                    fp = os.path.join(top, f)
                    target_ns = self._get_target_ns(fp)
                    imports[target_ns].append(fp)
        
        for k,v in imports.iteritems():
            if len(v) > 1:
                base_schema = self._get_include_base_schema(v)
                imports[k] = base_schema
            else:
                imports[k] = v[0]
    
        return imports
    
    def _build_wrapper_schema(self, import_dict):
        '''Creates a wrapper schema that imports all namespaces defined by the input dictionary. This enables
        validation of instance documents that refer to multiple namespaces and schemas
        
        Keyword Arguments
        import_dict - a dictionary of the form {namespace : path to schema} that will be used to build the list of xs:import statements
        '''
        schema_txt = '''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://stix.mitre.org/tools/validator" elementFormDefault="qualified" attributeFormDefault="qualified"/>'''
        root = etree.fromstring(schema_txt)
        
        tag_import = "{%s}import" % (self.NS_XML_SCHEMA)
        for ns, list_schemaloc in import_dict.iteritems():
            schemaloc = list_schemaloc
            schemaloc = schemaloc.replace("\\", "/")
            attrib = {'namespace' : ns, 'schemaLocation' : schemaloc}
            el_import = etree.Element(tag_import, attrib=attrib)
            root.append(el_import)
    
        return root

    def _extract_schema_locations(self, root):
        schemaloc_dict = {}
        
        tag_schemaloc = "{%s}schemaLocation" % (self.NS_XML_SCHEMA_INSTANCE)
        schemaloc = root.attrib[tag_schemaloc].split()
        schemaloc_pairs = zip(schemaloc[::2], schemaloc[1::2])
        
        for ns, loc in schemaloc_pairs:
            schemaloc_dict[ns] = loc
        
        return schemaloc_dict
    
    def _build_result_dict(self, result, errors=None):
        d = {}
        d['result'] = result
        if errors: 
            if not hasattr(errors, "__iter__"):
                errors = [errors]
            d['errors'] = errors
        return d
    
    def validate(self, instance_doc):
        '''Validates an instance documents.
        
        Returns a tuple of where the first item is the boolean validation
        result and the second is the validation error if there was one.
        
        Keyword Arguments
        instance_doc - a filename, file-like object, etree._Element, or etree._ElementTree to be validated
        '''
        if not(self.__use_schemaloc or self.__imports):
            return (False, "No schemas to validate against! Try instantiating XmlValidator with use_schemaloc=True or setting the schema_dir")
        
        if isinstance(instance_doc, etree._Element):
            instance_root = instance_doc
        elif isinstance(instance_doc, etree._ElementTree):
            instance_root = instance_doc.getroot()
        else:
            try:
                et = etree.parse(instance_doc)
                instance_root = et.getroot()
            except etree.XMLSyntaxError as e:
                return self._build_result_dict(False, str(e))
            
        if self.__use_schemaloc:
            try:
                required_imports = self._extract_schema_locations(instance_root)
            except KeyError as e:
                return (False, "No schemaLocation attribute set on instance document. Unable to validate")
        else:
            required_imports = {}
            for prefix, ns in instance_root.nsmap.iteritems():
                schemaloc = self.__imports.get(ns)
                if schemaloc:
                    required_imports[ns] = schemaloc

        if not required_imports:
            return (False, "Unable to determine schemas to validate against")

        wrapper_schema_doc = self._build_wrapper_schema(import_dict=required_imports)
        xmlschema = etree.XMLSchema(wrapper_schema_doc)
        
        isvalid = xmlschema.validate(instance_root)
        if isvalid:
            return self._build_result_dict(True)
        else:
            return self._build_result_dict(False, [str(x) for x in xmlschema.error_log])
            

class STIXValidator(XmlValidator):
    '''Schema validates STIX v1.1 documents and checks best practice guidance'''
    __stix_version__ = "1.1"
    
    PREFIX_STIX_CORE = 'stix'
    PREFIX_CYBOX_CORE = 'cybox'
    PREFIX_STIX_INDICATOR = 'indicator'
    
    NS_STIX_CORE = "http://stix.mitre.org/stix-1"
    NS_STIX_INDICATOR = "http://stix.mitre.org/Indicator-2"
    NS_CYBOX_CORE = "http://cybox.mitre.org/cybox-2"
    
    NS_MAP = {PREFIX_CYBOX_CORE : NS_CYBOX_CORE,
              PREFIX_STIX_CORE : NS_STIX_CORE,
              PREFIX_STIX_INDICATOR : NS_STIX_INDICATOR}
    
    def __init__(self, schema_dir=None, use_schemaloc=False, best_practices=False):
        super(STIXValidator, self).__init__(schema_dir, use_schemaloc)
        self.best_practices = best_practices
        
    def _check_id_presence_and_format(self, instance_doc):
        '''Checks that the core STIX/CybOX constructs in the STIX instance document
        have ids and that each id is formatted as [ns_prefix]:[object-type]-[GUID].
        
        Returns a dictionary of lists. Each dictionary has the following keys:
        no_id - a list of etree Element objects for all nodes without ids
        format - a list of etree Element objects with ids not formatted as [ns_prefix]:[object-type]-[GUID]
    
        Keyword Arguments
        instance_doc - an etree Element object for a STIX instance document
        '''
        return_dict = {'no_id' : [],
                       'format' : []}
        
        elements_to_check = ['stix:Campaign',
                             'stix:Course_Of_Action',
                             'stix:Exploit_Target',
                             'stix:Incident',
                             'stix:Indicator',
                             'stix:STIX_Package',
                             'stix:Threat_Actor',
                             'stix:TTP',
                             'cybox:Observable',
                             'cybox:Object',
                             'cybox:Event',
                             'cybox:Action']
    
        for tag in elements_to_check:
            xpath = ".//%s" % (tag)
            elements = instance_doc.xpath(xpath, namespaces=self.NS_MAP)
            
            for e in elements:
                try:
                    if not re.match(r'\w+:\w+-', e.attrib['id']): # not the best regex
                        return_dict['format'].append({'tag':e.tag, 'id':e.attrib['id'], 'line_number':e.sourceline})
                except KeyError as ex:
                    return_dict['no_id'].append({'tag':e.tag, 'line_number':e.sourceline})
            
        return return_dict
    
    def _check_duplicate_ids(self, instance_doc):
        '''Looks for duplicate ids in a STIX instance document. 
        
        Returns a dictionary of lists. Each dictionary uses the offending
        id as a key, which points to a list of etree Element nodes which
        use that id.
        
        Keyword Arguments
        instance_doc - an etree.Element object for a STIX instance document
        '''
        dict_id_nodes = defaultdict(list)
        dup_dict = {}
        xpath_all_nodes_with_ids = "//*[@id]"
        
        all_nodes_with_ids = instance_doc.xpath(xpath_all_nodes_with_ids)
        for node in all_nodes_with_ids:
            dict_id_nodes[node.attrib['id']].append(node)
        
        for id,node_list in dict_id_nodes.iteritems():
            if len(node_list) > 1:
                dup_dict[id] = [{'tag':node.tag, 'line_number':node.sourceline} for node in node_list]
        
        return dup_dict
    
    def _check_idref_resolution(self, instance_doc):
        '''Checks that all idref attributes in the input document resolve to a local element.
        Returns a list etree.Element nodes with unresolveable idrefs.
        
        Keyword Arguments
        instance_doc - an etree.Element object for a STIX instance document
        '''
        list_unresolved_ids = []
        xpath_all_idrefs = "//*[@idref]"
        xpath_all_ids = "//@id"
        
        all_idrefs = instance_doc.xpath(xpath_all_idrefs)
        all_ids = instance_doc.xpath(xpath_all_ids)
        
        for node in all_idrefs:
            if node.attrib['idref'] not in all_ids:
                d = {'tag': node.tag,
                     'idref': node.attrib['idref'],
                     'line_number' : node.sourceline}
                list_unresolved_ids.append(d)
                
        return list_unresolved_ids
                
    def _check_idref_with_content(self, instance_doc):
        '''Looks for elements that have an idref attribute set, but also have content.
        Returns a list of etree.Element nodes.
        
        Keyword Arguments:
        instance_doc - an etree.Element object for a STIX instance document
        '''
        list_nodes = []
        xpath = "//*[@idref]"
        nodes = instance_doc.xpath(xpath)
        
        for node in nodes:
            if node.text or len(node) > 0:
                d = {'tag' : node.tag,
                     'idref' : node.attrib['idref'],
                     'line_number' : node.sourceline}
                list_nodes.append(node)
                
        return list_nodes
    
    def _check_indicator_practices(self, instance_doc):
        '''Looks for STIX Indicators that are missing a Title, Description, Type, Valid_Time_Position, 
        Indicated_TTP, and/or Confidence
        
        Returns a list of dictionaries. Each dictionary has the following keys:
        id - the id of the indicator
        node - the etree.Element object for the indicator
        missing - a list of constructs missing from the indicator
        
        Keyword Arguments
        instance_doc - etree Element for a STIX sinstance document
        '''
        list_indicators = []
        xpath = "//%s:Indicator | %s:Indicator" % (self.PREFIX_STIX_CORE, self.PREFIX_STIX_INDICATOR)
        
        nodes = instance_doc.xpath(xpath, namespaces=self.NS_MAP)
        for node in nodes:
            dict_indicator = defaultdict(list)
            if not node.attrib.get('idref'): # if this is not an idref node, look at its content
                if node.find('{%s}Title' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('Title')
                if node.find('{%s}Description' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('Description')
                if node.find('{%s}Type' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('Type')
                if node.find('{%s}Valid_Time_Position' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('Valid_Time_Position')
                if node.find('{%s}Indicated_TTP' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('TTP')
                if node.find('{%s}Confidence' % (self.NS_STIX_INDICATOR)) is None:
                    dict_indicator['missing'].append('Confidence')
                
                if dict_indicator:
                    dict_indicator['id'] = node.attrib.get('id')
                    dict_indicator['line_number'] = node.sourceline
                    list_indicators.append(dict_indicator)
                
        return list_indicators
 
    def _check_root_element(self, instance_doc):
        d = {}
        if instance_doc.tag != "{%s}STIX_Package" % (self.NS_STIX_CORE):
            d['tag'] = instance_doc.tag
            d['line_number'] = instance_doc.sourceline
        return d
            
 
    def check_best_practices(self, instance_doc):
        '''Checks that a STIX instance document is following best practice guidance.
        
        Looks for the following:
        + idrefs that do not resolve locally
        + elements with duplicate ids
        + elements without ids
        + elements with ids not formatted as [ns_prefix]:[object-type]-[GUID]
        + indicators missing a Title, Description, Type, Valid_Time_Position, Indicated_TTP, and/or Confidence
        
        Returns a dictionary of lists and other dictionaries. This is maybe not ideal but workable.
        
        Keyword Arguments
        instance_doc - a filename, file-like object, etree._Element or etree.ElementTree for a STIX instance document
        '''
        
        if isinstance(instance_doc, etree._Element):
            root = instance_doc
        elif isinstance(instance_doc, etree._ElementTree):
            root = instance_doc.getroot()
        elif isinstance(instance_doc, basestring):
            tree = etree.parse(instance_doc)
            root = tree.getroot()
        else:
            instance_doc.seek(0)
            tree = etree.parse(instance_doc)
            root = tree.getroot()
        
        root_element = self._check_root_element(root)
        list_unresolved_idrefs = self._check_idref_resolution(root)
        dict_duplicate_ids = self._check_duplicate_ids(root)
        dict_presence_and_format = self._check_id_presence_and_format(root)
        list_idref_with_content = self._check_idref_with_content(root)
        list_indicators = self._check_indicator_practices(root)
        
        d = {}
        if root_element:
            d['root_element'] = root_element
        if list_unresolved_idrefs:
            d['unresolved_idrefs'] = list_unresolved_idrefs
        if dict_duplicate_ids:
            d['duplicate_ids'] = dict_duplicate_ids
        if dict_presence_and_format:
            if dict_presence_and_format.get('no_id'):
                d['missing_ids'] = dict_presence_and_format['no_id']
            if dict_presence_and_format.get('format'):
                d['id_format'] = dict_presence_and_format['format']
        if list_idref_with_content:
            d['idref_with_content'] = list_idref_with_content
        if list_indicators:
            d['indicator_suggestions'] = list_indicators
        
        return d
    
    def validate(self, instance_doc):
        '''Validates a STIX document and checks best practice guidance if STIXValidator
        was initialized with best_practices=True.
        
        Best practices will not be checked if the document is schema-invalid.
        
        Keyword Arguments
        instance_doc - a filename, file-like object, etree._Element or etree.ElementTree for a STIX instance document
        '''
        result_dict = super(STIXValidator, self).validate(instance_doc)
        
        isvalid = result_dict['result']
        if self.best_practices and isvalid:
            best_practice_warnings = self.check_best_practices(instance_doc)
        else:
            best_practice_warnings = None
        
        if best_practice_warnings:
            result_dict['best_practice_warnings'] = best_practice_warnings
             
        return result_dict

class SchematronValidator(object):
    NS_SVRL = "http://purl.oclc.org/dsdl/svrl"
    NS_SCHEMATRON = "http://purl.oclc.org/dsdl/schematron"
    NS_SAXON = "http://icl.com/saxon" # libxml2 requires this namespace instead of http://saxon.sf.net/
    NS_SAXON_SF_NET = "http://saxon.sf.net/"
    
    def __init__(self, schematron=None):
        self.schematron = None # isoschematron.Schematron instance
        self._init_schematron(schematron)
        
    def _init_schematron(self, schematron):
        '''Returns an instance of lxml.isoschematron.Schematron'''
        if schematron is None:
            self.schematron = None
            return
        elif not (isinstance(schematron, etree._Element) or isinstance(schematron, etree._ElementTree)):
            tree = etree.parse(schematron)
        else:
            tree = schematron
            
        self.schematron = isoschematron.Schematron(tree, store_report=True, store_xslt=True, store_schematron=True)
        
    def get_xslt(self):
        if not self.schematron:
            return None
        return self.schematron.validator_xslt
      
    def get_schematron(self):
        if not self.schematron:
            return None 
        return self.schematron.schematron
    
    def _build_result_dict(self, result, report=None):
        '''Creates a dictionary to be returned by the validate() method.'''
        d = {}
        d['result'] = result
        if report:
                d['report'] = report
        return d
    
    def _get_schematron_errors(self, validation_report):
        '''Returns a list of SVRL failed-assert and successful-report elements.'''
        xpath = "//svrl:failed-assert | //svrl:successful-report"
        errors = validation_report.xpath(xpath, namespaces={'svrl':self.NS_SVRL})
        return errors
    
    def _get_error_line_numbers(self, d_error, tree):
        '''Returns a sorted list of line numbers for a given Schematron error.'''
        locations = d_error['locations']
        nsmap = d_error['nsmap']
        
        line_numbers = []
        for location in locations:
            ctx_node = tree.xpath(location, namespaces=nsmap)[0]
            if ctx_node.sourceline not in line_numbers: 
                line_numbers.append(ctx_node.sourceline)
        
        line_numbers.sort()
        return line_numbers
    
    def _build_error_dict(self, errors, instance_tree, report_line_numbers=True):
        '''Returns a dictionary representation of the SVRL validation report:
        d0 = { <Schemtron error message> : d1 }
        
        d1 = { "locations" : A list of XPaths to context nodes,
               "line_numbers" : A list of line numbers where the error occurred,
               "test" : The Schematron evaluation expression used,
               "text" : The Schematron error message }
        
        '''
        d_errors = {}
        
        for error in errors:
            text = error.find("{%s}text" % self.NS_SVRL).text
            location = error.attrib.get('location')
            test = error.attrib.get('test') 
            if text in d_errors:
                d_errors[text]['locations'].append(location)
            else:
                d_errors[text] = {'locations':[location], 'test':test, 'nsmap':error.nsmap, 'text':text}
        
        if report_line_numbers:
            for d_error in d_errors.itervalues():
                line_numbers = self._get_error_line_numbers(d_error, instance_tree)
                d_error['line_numbers'] = line_numbers
        
        return d_errors
    
    def _build_error_report_dict(self, validation_report, instance_tree, report_line_numbers=True): 
        errors = self._get_schematron_errors(validation_report)
        d_errors = self._build_error_dict(errors, instance_tree, report_line_numbers)
        report_dict = defaultdict(list)
        for msg, d in d_errors.iteritems():
            d_error = {'error' : msg}
            if 'line_numbers' in d:
                d_error['line_numbers'] = d['line_numbers']
            report_dict['errors'].append(d_error)
            
        return report_dict
    
    def validate(self, instance, report_line_numbers=True):
        '''Validates an XML instance document.
        
        Arguments:
        report_line_numbers : Includes error line numbers in the returned dictionary.
                              This may slow performance.
                              
        '''
        if not self.schematron:
            raise Exception('Schematron document not set. Cannot validate. Call init_schematron(...) and retry.')
        try:
            if isinstance(instance, etree._Element):
                tree = etree.ElementTree(instance)
            elif isinstance(instance, etree._ElementTree):
                tree = instance
            else:
                tree = etree.parse(instance)
            
            result = self.schematron.validate(tree)
            report = self._build_error_report_dict(self.schematron.validation_report, tree, report_line_numbers)

            if len(report['errors']) > 0:
                report = self._build_error_report_dict(self.schematron.validation_report, tree, report_line_numbers)
                return self._build_result_dict(result, report)
            else:
                return self._build_result_dict(result)
            
        except etree.ParseError as e:
            return self._build_result_dict(False, [str(e)])    

class ProfileValidator(SchematronValidator):
    NS_STIX = "http://stix.mitre.org/stix-1"
    
    def __init__(self, profile_fn):
        '''Initializes an instance of ProfileValidator.'''
        profile = self._open_profile(profile_fn)
        schema = self._parse_profile(profile)
        super(ProfileValidator, self).__init__(schematron=schema)
    
    def _build_rule_dict(self, worksheet):
        '''Builds a dictionary representation of the rules defined by a STIX profile document.'''
        d = defaultdict(list)
        for i in xrange(1, worksheet.nrows):
            if not any(self._get_cell_value(worksheet, i, x) for x in xrange(0, worksheet.ncols)): # empty row
                continue
            if not self._get_cell_value(worksheet, i, 1): # assume this is a label row
                context = self._get_cell_value(worksheet, i, 0)
                continue

            field = self._get_cell_value(worksheet, i, 0)
            occurrence = self._get_cell_value(worksheet, i, 1).lower()
            xsi_types = self._get_cell_value(worksheet, i, 3)
            allowed_values = self._get_cell_value(worksheet, i, 4)
            
            list_xsi_types = [x.strip() for x in xsi_types.split(',')] if xsi_types else []
            list_allowed_values = [x.strip() for x in allowed_values.split(',')] if allowed_values else []
            
            
            if occurrence in ('required', 'prohibited') or len(list_xsi_types) > 0 or len(list_allowed_values) > 0: # ignore rows with no rules
                d[context].append({'field' : field,
                                   'occurrence' : occurrence,
                                   'xsi_types' : list_xsi_types,
                                   'allowed_values' : list_allowed_values})
        return d
    
    def _add_root_test(self, pattern, nsmap):
        '''Adds a root-level test that requires the root element of a STIX
        document be a STIX_Package'''
        ns_stix = "http://stix.mitre.org/stix-1"
        rule_element = self._add_element(pattern, "rule", context="/")
        text = "The root element must be a STIX_Package instance"
        test = "%s:STIX_Package" % nsmap.get(ns_stix, 'stix')
        element = etree.XML('''<assert xmlns="%s" test="%s" role="error">%s [<value-of select="saxon:line-number()"/>]</assert> ''' % (self.NS_SCHEMATRON, test, text))
        rule_element.append(element)

    def _add_required_test(self, rule_element, entity_name, context):
        '''Adds a test to the rule element checking for the presence of a required STIX field.'''
        entity_path = "%s/%s" % (context, entity_name)
        text = "%s is required by this profile" % (entity_path)
        test = entity_name
        element = etree.XML('''<assert xmlns="%s" test="%s" role="error">%s [<value-of select="saxon:line-number()"/>]</assert> ''' % (self.NS_SCHEMATRON, test, text))
        rule_element.append(element)
    
    def _add_prohibited_test(self, rule_element, entity_name, context):
        '''Adds a test to the rule element checking for the presence of a prohibited STIX field.'''
        entity_path = "%s/%s" % (context, entity_name) if entity_name.startswith("@") else context
        text = "%s is prohibited by this profile" % (entity_path)
        test_field = entity_name if entity_name.startswith("@") else "true()"
        element = etree.XML('''<report xmlns="%s" test="%s" role="error">%s [<value-of select="saxon:line-number()"/>]</report> ''' % (self.NS_SCHEMATRON, test_field, text))
        rule_element.append(element)
    
    def _add_allowed_xsi_types_test(self, rule_element, context, entity_name, allowed_xsi_types):
        '''Adds a test to the rule element which corresponds to values found in the Allowed Implementations
        column of a STIX profile document.'''
        entity_path = "%s/%s" % (context, entity_name)
                
        if allowed_xsi_types:
            test = " or ".join("@xsi:type='%s'" % (x) for x in allowed_xsi_types)
            text = 'The allowed xsi:types for %s are %s' % (entity_path, allowed_xsi_types)
            element = etree.XML('''<assert xmlns="%s" test="%s" role="error">%s [<value-of select="saxon:line-number()"/>]</assert> ''' % (self.NS_SCHEMATRON, test, text))
            rule_element.append(element)
    
    def _add_allowed_values_test(self, rule_element, context, entity_name, allowed_values):
        '''Adds a test to the rule element corresponding to values found in the Allowed Values
        column of a STIX profile document.
        
        '''
        entity_path = "%s/%s" % (context, entity_name)
        text = "The allowed values for %s are %s" % (entity_path, allowed_values)
        
        if entity_name.startswith('@'):
            test = " or ".join("%s='%s'" % (entity_name, x) for x in allowed_values)
        else:
            test = " or ".join(".='%s'" % (x) for x in allowed_values)
        
        element = etree.XML('''<assert xmlns="%s" test="%s" role="error">%s [<value-of select="saxon:line-number()"/>]</assert> ''' % (self.NS_SCHEMATRON, test, text))
        rule_element.append(element)
    
    def _create_rule_element(self, context):
        '''Returns an etree._Element representation of a Schematron rule element.'''
        rule = etree.Element("{%s}rule" % self.NS_SCHEMATRON)
        rule.set('context', context)
        return rule
    
    def _add_rules(self, pattern_element, selectors, field_ns, tests):
        '''Adds all Schematron rules and tests to the overarching Schematron
        <pattern> element. Each rule and test corresponds to entries found
        in the STIX profile document.
        
        '''
        d_rules = {} # context : rule_element
        for selector in selectors:
            for d_test in tests:
                field = d_test['field']
                occurrence = d_test['occurrence']
                allowed_values = d_test['allowed_values']
                allowed_xsi_types = d_test['xsi_types']
                
                if field.startswith("@"):
                    entity_name = field
                else:
                    entity_name = "%s:%s" % (field_ns, field)
                
                if occurrence == "required":
                    ctx = selector
                    rule = d_rules.setdefault(ctx, self._create_rule_element(ctx))
                    self._add_required_test(rule, entity_name, ctx)
                elif occurrence == "prohibited":
                    if entity_name.startswith("@"):
                        ctx = selector
                    else:
                        ctx = "%s/%s" % (selector, entity_name)
                    
                    rule = d_rules.setdefault(ctx, self._create_rule_element(ctx))
                    self._add_prohibited_test(rule, entity_name, ctx)
                
                if allowed_values or allowed_xsi_types:
                    if entity_name.startswith('@'):
                        ctx = selector
                    else:
                        ctx = "%s/%s" % (selector, entity_name)
                        
                    rule = d_rules.setdefault(ctx, self._create_rule_element(ctx))
                    if allowed_values:
                        self._add_allowed_values_test(rule, selector, entity_name, allowed_values)
                    if allowed_xsi_types:
                        self._add_allowed_xsi_types_test(rule, selector, entity_name, allowed_xsi_types)
        
        for rule in d_rules.itervalues():            
            pattern_element.append(rule)
    
    def _build_schematron_xml(self, rules, nsmap, instance_map):
        '''Returns an etree._Element instance representation of the STIX profile'''
        root = etree.Element("{%s}schema" % self.NS_SCHEMATRON, nsmap={None:self.NS_SCHEMATRON})
        pattern = self._add_element(root, "pattern", id="STIX_Schematron_Profile")
        self._add_root_test(pattern, nsmap) # check the root element of the document
        
        for label, tests in rules.iteritems():
            d_instances = instance_map[label]
            selectors = d_instances['selectors']
            field_ns_alias = d_instances['ns_alias']
            self._add_rules(pattern, selectors, field_ns_alias, tests)
        
        self._map_ns(root, nsmap) # add namespaces to the schematron document
        return root
    
    def _parse_namespace_worksheet(self, worksheet):
        '''Parses the Namespaces worksheet of the profile. Returns a dictionary representation:
        
        d = { <namespace> : <namespace alias> }
        
        By default, entries for http://stix.mitre.org/stix-1 and http://icl.com/saxon are added.
        
        '''
        nsmap = {self.NS_STIX : 'stix',
                 self.NS_SAXON : 'saxon'}
        for i in xrange(1, worksheet.nrows): # skip the first row
            if not any(self._get_cell_value(worksheet, i, x) for x in xrange(0, worksheet.ncols)): # empty row
                continue
            
            ns = self._get_cell_value(worksheet, i, 0)
            alias = self._get_cell_value(worksheet, i, 1)

            if not (ns or alias):
                raise Exception("Missing namespace or alias: unable to parse Namespaces worksheet")
            
            nsmap[ns] = alias
        return nsmap      
    
    def _parse_instance_mapping_worksheet(self, worksheet, nsmap):
        '''Parses the supplied Instance Mapping worksheet and returns a dictionary representation.
        
        d0  = { <STIX type label> : d1 }
        d1  = { 'selectors' : XPath selectors to instances of the XML datatype',
                'ns' : The namespace where the STIX type is defined,
                'ns_alias' : The namespace alias associated with the namespace }
                
        '''
        instance_map = {}
        for i in xrange(1, worksheet.nrows):
            if not any(self._get_cell_value(worksheet, i, x) for x in xrange(0, worksheet.ncols)): # empty row
                continue
            
            label = self._get_cell_value(worksheet, i, 0)
            selectors = [x.strip() for x in self._get_cell_value(worksheet, i, 1).split(",")]
            ns = self._get_cell_value(worksheet, i, 2)
            ns_alias = nsmap[ns]
            
            if not (label or selectors or ns):
                raise Exception("Missing label, instance selector and/or namespace for %s in Instance Mapping worksheet" % label)
            
            instance_map[label] = {'selectors':selectors, 'ns':ns, 'ns_alias':ns_alias}
        return instance_map
    
    def _parse_profile(self, profile):
        '''Converts the supplied STIX profile into a Schematron representation. The
        Schematron schema is returned as a etree._Element instance.
        
        '''
        overview_ws = profile.sheet_by_name("Overview")
        namespace_ws = profile.sheet_by_name("Namespaces")
        instance_mapping_ws = profile.sheet_by_name("Instance Mapping")
                
        all_rules = defaultdict(list)
        for worksheet in profile.sheets():
            if worksheet.name not in ("Overview", "Namespaces", "Instance Mapping"):
                rules = self._build_rule_dict(worksheet)
                for context,d in rules.iteritems():
                    all_rules[context].extend(d)

        namespaces = self._parse_namespace_worksheet(namespace_ws)
        instance_mapping = self._parse_instance_mapping_worksheet(instance_mapping_ws, namespaces)
        schema = self._build_schematron_xml(all_rules, namespaces, instance_mapping)
        
        self._unload_workbook(profile)
        return schema
            
    def _map_ns(self, schematron, nsmap):
        '''Adds <ns> nodes to the supplied schematron document for each entry
        supplied by the nsmap.
        
        '''
        for ns, prefix in nsmap.iteritems():
            ns_element = etree.Element("{%s}ns" % self.NS_SCHEMATRON)
            ns_element.set("prefix", prefix)
            ns_element.set("uri", ns)
            schematron.insert(0, ns_element)
            
    def _add_element(self, node, name, text=None, **kwargs):
        '''Adds an etree._Element child to the supplied node. The child node is returned'''
        child = etree.SubElement(node, "{%s}%s" % (self.NS_SCHEMATRON, name))
        if text:
            child.text = text
        for k,v in kwargs.iteritems():
            child.set(k, v)
        return child
    
    def _unload_workbook(self, workbook):
        '''Unloads the xlrd workbook.'''
        for worksheet in workbook.sheets():
            workbook.unload_sheet(worksheet.name)
            
    def _get_cell_value(self, worksheet, row, col):
        '''Returns the worksheet cell value found at (row,col).'''
        if not worksheet:
            raise Exception("worksheet value was NoneType")
        value = str(worksheet.cell_value(row, col))
        return value
    
    def _convert_to_string(self, value):
        '''Returns the str(value) or an 8-bit string version of value encoded as UTF-8.'''
        if isinstance(value, unicode):
            return value.encode("UTF-8")
        else:
            return str(value)
    
    def _open_profile(self, filename):
        '''Returns xlrd.open_workbook(filename) or raises an Exception if the
        filename extension is not .xlsx or the open_workbook() call fails.
        
        '''
        if not filename.lower().endswith(".xlsx"):
            raise Exception("File must have .XLSX extension. Filename provided: %s" % filename)
        try:
            return xlrd.open_workbook(filename)
        except:
            raise Exception("File does not seem to be valid XLSX.")
    
    def validate(self, instance_doc):
        '''Validates an XML instance document against a STIX profile.'''
        return super(ProfileValidator, self).validate(instance_doc, report_line_numbers=False)
    
    def _build_error_dict(self, errors, instance_doc, report_line_numbers=False):
        '''Overrides SchematronValidator._build_error_dict(...).
        
        Returns a dictionary representation of the SVRL validation report:
        d0 = { <Schemtron error message> : d1 }
        
        d1 = { "locations" : A list of XPaths to context nodes,
               "line_numbers" : A list of line numbers where the error occurred,
               "test" : The Schematron evaluation expression used,
               "text" : The Schematron error message }
        
        '''
        d_errors = {}
        for error in errors:
            text = error.find("{%s}text" % self.NS_SVRL).text
            location = error.attrib.get('location')
            test = error.attrib.get('test')
             
            line_number = text.split(" ")[-1][1:-1]
            text = text[:text.rfind(' [')]
             
            if text in d_errors:
                d_errors[text]['locations'].append(location)
                d_errors[text]['line_numbers'].append(line_number)
            else:
                d_errors[text] = {'locations':[location], 'test':test, 'nsmap':error.nsmap, 'text':text, 'line_numbers':[line_number]}
        return d_errors
    
    def get_xslt(self):
        '''Overrides SchematronValidator.get_xslt()
        
        Returns an lxml.etree._ElementTree representation of the ISO Schematron skeleton generated
        XSLT translation of a STIX profile.
        
        The ProfileValidator uses the extension function saxon:line-number() for reporting line numbers.
        This function is stripped along with any references to the Saxon namespace from the exported
        XSLT. This is due to compatibility issues between Schematron/XSLT processing libraries. For
        example, SaxonPE/EE expects the Saxon namespace to be "http://saxon.sf.net/" while libxslt 
        expects it to be "http://icl.com/saxon". The freely distributed SaxonHE library does not support 
        Saxon extension functions at all.
        
        '''
        if not self.schematron:
            return None
        
        s = etree.tostring(self.schematron.validator_xslt)
        s = s.replace(' [<axsl:text/><axsl:value-of select="saxon:line-number()"/><axsl:text/>]', '')
        s = s.replace('xmlns:saxon="http://icl.com/saxon"', '')
        s = s.replace('<svrl:ns-prefix-in-attribute-values uri="http://icl.com/saxon" prefix="saxon"/>', '')
        return etree.ElementTree(etree.fromstring(s))
      
    def get_schematron(self):
        '''Overrides SchematronValidator.get_schematron()
        
        Returns an lxml.etree._ElementTree representation of the ISO Schematron translation of a STIX profile.
        
        The ProfileValidator uses the extension function saxon:line-number() for reporting line numbers.
        This function is stripped along with any references to the Saxon namespace from the exported
        XSLT. This is due to compatibility issues between Schematron/XSLT processing libraries. For
        example, SaxonPE/EE expects the Saxon namespace to be "http://saxon.sf.net/" while libxslt 
        expects it to be "http://icl.com/saxon". The freely distributed SaxonHE library does not support 
        Saxon extension functions at all.
        
        '''
        if not self.schematron:
            return None
        
        s = etree.tostring(self.schematron.schematron)
        s = s.replace(' [<value-of select="saxon:line-number()"/>]', '')
        s = s.replace('<ns prefix="saxon" uri="http://icl.com/saxon"/>', '')
        return etree.ElementTree(etree.fromstring(s))