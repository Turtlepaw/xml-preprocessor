# XML Preprocessor
# © Gondwana Software 2024.
# Returns 0 on success.

import copy
import os
import re
import sys
import xml.etree.ElementTree as xmlpp_ET

class xmlpp_error(Exception):   # custom Exception class
    def __init__(self, message):
        print(f"❌ Preprocessor error: {message}")
        print("   For more info, run preprocessor with -d argument")
        exit(1)

xmlpp_DEBUG = False
xmlpp_source_file = xmlpp_dest_file = None
xmlpp_symbols = {}  # associative array (disctionary) of <Symbol> elements, indexed by [id]

def xmlpp_parse_args():     # parse command-line arguments
    xmlpp_OVERWRITE = False
    xmlpp_USAGE_ERROR = False
    global xmlpp_source_file, xmlpp_dest_file, xmlpp_DEBUG
    for xmlpp_i, xmlpp_arg in enumerate(sys.argv[1:], start=1):
        if xmlpp_arg == "-d": xmlpp_DEBUG = True
        elif xmlpp_arg == "-y": xmlpp_OVERWRITE = True
        elif xmlpp_arg[0] == '-': xmlpp_USAGE_ERROR = True
        elif xmlpp_source_file is not None: xmlpp_dest_file = xmlpp_arg
        else: xmlpp_source_file = xmlpp_arg

    if xmlpp_source_file is None or xmlpp_dest_file is None or xmlpp_USAGE_ERROR:
        print("XML Preprocessor 1.00")
        print("Usage: preprocess.py sourceFile destinationFile [-d] [-y]")
        print("   -d prints debugging info")
        print("   -y overwrites destinationFile")
        exit(1)

    if not os.path.exists(xmlpp_source_file):
        raise xmlpp_error("can't find "+xmlpp_source_file)

    if os.path.exists(xmlpp_dest_file) and not xmlpp_OVERWRITE:
        xmlpp_overwrite_input = input("Desination file already exists; overwrite it (y/n)? ")
        if (xmlpp_overwrite_input != "y"): exit(2)

def xmlpp_read_source(xmlpp_source_file):
    global xmlpp_tree, xmlpp_root
    xmlpp_tree = xmlpp_ET.parse(xmlpp_source_file)
    xmlpp_root = xmlpp_tree.getroot()

def xmlpp_exec_all_definitions():   # execute all <Define> elements and delete them
    if xmlpp_DEBUG: print("Executing <Define>s...")

    def xmlpp_exec_definitions(xmlpp_text):
        def xmlpp_find_indent_size(xmlpp_firstLine):
            for xmlpp_index, xmlpp_char in enumerate(xmlpp_firstLine):
                if xmlpp_char != ' ':
                    return xmlpp_index
            return -1   # all characters are spaces

        # Remove first line (text following <Define>):
        xmlpp_firstEOLindex = xmlpp_text.find('\n')
        if xmlpp_firstEOLindex != -1:
            xmlpp_text = xmlpp_text[xmlpp_firstEOLindex+1:]
        if not xmlpp_text.isspace():
            xmlpp_lines = xmlpp_text.split('\n')
            xmlpp_indent_size = xmlpp_find_indent_size(xmlpp_lines[0])
            xmlpp_processed_lines = []
            for xmlpp_line in xmlpp_lines:
                xmlpp_processed_line = xmlpp_line[xmlpp_indent_size:] if xmlpp_line.startswith(' ' * xmlpp_indent_size) else xmlpp_line.lstrip()
                xmlpp_processed_lines.append(xmlpp_processed_line)
            xmlpp_text = '\n'.join(xmlpp_processed_lines)
            #print("Indent size: ",xmlpp_indent_size)
            #print("Before strip:\n\""+el.text+"\"")
            #print("After strip:\n\""+xmlpp_text+"\"\n")
            if xmlpp_DEBUG: print("\n".join(["   " + line for line in xmlpp_text.split("\n")]))
            exec(xmlpp_text, globals())

    xmlpp_define_els = []
    for xmlpp_el in xmlpp_root.iter('Define'):
        # print("tag="+el.tag)
        if (xmlpp_el.text):
            xmlpp_exec_definitions(xmlpp_el.text)
        if (xmlpp_el.tail):
            xmlpp_exec_definitions(xmlpp_el.tail)
        #xmlpp_root.remove(el) # delete <Define> element
        xmlpp_define_els.append(xmlpp_el)

    for xmlpp_el in xmlpp_define_els:
        xmlpp_root.remove(xmlpp_el)

def xmlpp_dump_el(xmlpp_el, xmlpp_el_name, xmlpp_indent=0):     # used with xmlpp_DEBUG
    def xmlpp_dump_recurse(xmlpp_el, xmlpp_indent=0):
        for xmlpp_child_el in xmlpp_el:
            print(f"{' '*xmlpp_indent}{xmlpp_child_el.tag}")
            xmlpp_dump_recurse(xmlpp_child_el, xmlpp_indent+3)

    print(f"{' '*xmlpp_indent}Dump of {xmlpp_el_name}:")
    xmlpp_dump_recurse(xmlpp_el,  xmlpp_indent+3)
    #for xmlpp_child_el in xmlpp_el:
    #    print(f"   {xmlpp_child_el.tag}")

def xmlpp_extract_symbols():    # extract all <Symbol> elements and delete them
    global xmlpp_symbols

    if (xmlpp_DEBUG): print("\nExtracting <Symbols>...")

    xmlpp_symbol_els = []
    for xmlpp_symbol_el in xmlpp_root.iter('Symbol'):
        #print("symbol tag="+xmlpp_el.tag)
        xmlpp_symbol_id = xmlpp_symbol_el.attrib['id']
        if xmlpp_DEBUG:
            print(f"   <Symbol id={xmlpp_symbol_id}>")
            xmlpp_dump_el(xmlpp_symbol_el,"xmlpp_symbol_el", 6)
        xmlpp_symbols[xmlpp_symbol_id] = xmlpp_symbol_el
        #xmlpp_root.remove(xmlpp_el) # delete <Symbol> element from xmlpp_root
        xmlpp_symbol_els.append(xmlpp_symbol_el)    # to delete from root

    for xmlpp_el in xmlpp_symbol_els:
        xmlpp_root.remove(xmlpp_el)

def xmlpp_replace_all_uses(): # replace all <Use> elements
    if (xmlpp_DEBUG): print("\nReplacing <Use>s with <Symbol>s...")

    def xmlpp_replace_use(xmlpp_el):
        # Recursive.
        xmlpp_index = 0
        while xmlpp_index < len(xmlpp_el):
            xmlpp_child_el = xmlpp_el[xmlpp_index]
            if xmlpp_child_el.tag == "Use":
                xmlpp_href = xmlpp_child_el.get("href")
                if xmlpp_href[0] == '#':
                    xmlpp_href = xmlpp_href[1:]     # [1:] strips # from href
                if xmlpp_DEBUG:
                    print(f'   Replacing <Use href="#{xmlpp_href}">')
                xmlpp_symbol = xmlpp_symbols[xmlpp_href]
                xmlpp_delete_list = xmlpp_child_el.findall("Delete")
                xmlpp_transform_list = xmlpp_child_el.findall("Transform")
                #print(len(xmlpp_transform_list))

                # Remove <Use> el and any <Transform>s and <Delete>s within it:
                xmlpp_el.remove(xmlpp_child_el)

                # Clone <Symbol> so <Transform>s don't affect original <Symbol> or subsequent <Use>s:
                xmlpp_symbol_copy = copy.deepcopy(xmlpp_symbol)
                if xmlpp_DEBUG: xmlpp_dump_el(xmlpp_symbol_copy, "xmlpp_symbol_copy", 6)

                # Apply attributes specified in <Use> to all top-level elements in copy:
                #print(xmlpp_el.attrib)
                for xmlpp_symbol_el in xmlpp_symbol_copy:
                    for xmlpp_attrib_name, xmlpp_attrib_value in xmlpp_child_el.attrib.items():
                        if xmlpp_attrib_name != "href":
                            if xmlpp_DEBUG: print(f'      Setting attribute "{xmlpp_attrib_name}" on <{xmlpp_symbol_el.tag}>')
                            xmlpp_symbol_el.set(xmlpp_attrib_name, xmlpp_attrib_value)

                # recurse, just in case <Symbol> contains nested <Use>s:
                xmlpp_replace_use(xmlpp_symbol_copy)

                # Apply any <Delete> elements:
                if xmlpp_delete_list:
                    for xmlpp_delete in xmlpp_delete_list:
                        if xmlpp_DEBUG: print(f'      Applying <Delete href="{xmlpp_delete.attrib["href"]}">')
                        xmlpp_delete_els = xmlpp_symbol_copy.findall(xmlpp_delete.attrib["href"])
                        if len(xmlpp_delete_els) == 0:
                            raise xmlpp_error(f'Can\'t find any element to <Delete> with href="{xmlpp_delete.attrib["href"]}"')
                        for xmlpp_delete_el in xmlpp_delete_els:
                            xmlpp_parent = xmlpp_symbol_copy.find(xmlpp_delete.attrib["href"]+"/..")
                            xmlpp_parent.remove(xmlpp_delete_el)
                            if xmlpp_DEBUG: print("         Deleted an element")

                # Apply any <Transform> elements:
                if xmlpp_transform_list:
                    for xmlpp_transform in xmlpp_transform_list:
                        if xmlpp_DEBUG:
                            print(f'      Applying <Transform href="{xmlpp_transform.attrib["href"]}" target="{xmlpp_transform.attrib["target"]}"...>')
                        try:
                            xmlpp_transform_els = xmlpp_symbol_copy.findall(xmlpp_transform.attrib["href"])
                        except Exception as e:
                            raise xmlpp_error(f"{type(e).__name__} applying <Transform href=\"{xmlpp_transform.attrib['href']}\"...: {sys.exception()}. href may be invalid.")

                        if len(xmlpp_transform_els) == 0:
                            raise xmlpp_error(f'Can\'t find any element to <Transform> with href="{xmlpp_transform.attrib["href"]}"')
                        for xmlpp_transform_el in xmlpp_transform_els:
                            xmlpp_transform_el.set(xmlpp_transform.attrib["target"], xmlpp_transform.attrib["value"])
                            if xmlpp_DEBUG: print("         Transformed an element")

                # Insert copy of <Symbol>, potentially modified by <Transform>s, into tree:
                for xmlpp_symbol_el in xmlpp_symbol_copy:
                    #print("inserting "+xmlpp_symbol_el.tag)
                    xmlpp_el.insert(xmlpp_index, xmlpp_symbol_el)
                    xmlpp_index += 1   # skip over inserted elements coz they've already been recursed in case of nested <Use>s
            else:   # Not <Use>
                xmlpp_replace_use(xmlpp_child_el)   # recurse
                xmlpp_index += 1

    xmlpp_replace_use(xmlpp_root)

def xmlpp_replace_all_expressions(): # replace all {expression}s with their results
    if (xmlpp_DEBUG): print("\nEvaluating attribute {expression}s...")

    def xmlpp_evalStringWithExpressions(xmlpp_el, xmlpp_s, xmlpp_attrib_name=None):
        # Returns string with expressions replaced by values; False if no expressions found.

        def xmlpp_eval_parent(xmlpp_el, xmlpp_exp, xmlpp_attrib_name):
            # Returns arg with PARENT.attrib replaced by value of attrib in parent element.
            # If .attrib isn't specified, uses xmlpp_attrib_name.

            def xmlpp_eval_parent_terms(xmlpp_exp, xmlpp_regexp, xmlpp_attrib_name=None):
                def xmlpp_eval_parent_attrib(xmlpp_el, xmlpp_parent_attrib):
                    # Recurses; returns None if no ancestor has a value for xmlpp_parent_attrib.
                    if xmlpp_DEBUG: print(f'      Looking for <{xmlpp_el.tag} {xmlpp_parent_attrib}="...">')
                    if xmlpp_el not in xmlpp_parent_map:
                        return None
                    xmlpp_parent_el = xmlpp_parent_map[xmlpp_el]
                    xmlpp_parent_value = xmlpp_parent_el.get(xmlpp_parent_attrib)
                    if xmlpp_parent_value != None:
                        return xmlpp_parent_value
                    else:
                        return xmlpp_eval_parent_attrib(xmlpp_parent_el, xmlpp_parent_attrib)   # recurse

                # Returns string with PARENT terms replaced.
                xmlpp_matches = re.split(xmlpp_regexp, xmlpp_exp)
                #print(xmlpp_exp,xmlpp_matches)
                # Process all odd-numbered matches[]:
                for xmlpp_matchIndex in range(1, len(xmlpp_matches), 2):
                    xmlpp_parent_attrib = xmlpp_attrib_name if xmlpp_attrib_name else xmlpp_matches[xmlpp_matchIndex].split('.')[1]
                    #print(xmlpp_parent_attrib)
                    xmlpp_attrib_value = xmlpp_eval_parent_attrib(xmlpp_el, xmlpp_parent_attrib)
                    if xmlpp_attrib_value == None:
                        raise xmlpp_error('Can\'t find any PARENT of {0} with attribute named "{1}"'.format(xmlpp_el.tag, xmlpp_parent_attrib))
                    xmlpp_matches[xmlpp_matchIndex] = xmlpp_attrib_value
                return "".join(xmlpp_matches)

            # Process PARENT.attribName terms:
            xmlpp_exp = xmlpp_eval_parent_terms(xmlpp_exp, r'(PARENT\.[a-zA-Z-]+)')

            # Process PARENT (without attribName) terms:
            xmlpp_exp = xmlpp_eval_parent_terms(xmlpp_exp, r'(PARENT)', xmlpp_attrib_name)

            # Process SELF.attribName terms:
            #print('processing SELF...')     # TODO del
            xmlpp_matches = re.split(r'(SELF\.[a-zA-Z-]+)', xmlpp_exp)
            #print(xmlpp_exp,xmlpp_matches)
            # Process all odd-numbered matches[]:
            for xmlpp_matchIndex in range(1, len(xmlpp_matches), 2):
                xmlpp_self_attrib = xmlpp_matches[xmlpp_matchIndex].split('.')[1]
                xmlpp_attrib_value = xmlpp_el.get(xmlpp_self_attrib)
                if xmlpp_attrib_value == None:
                    raise xmlpp_error('Can\'t find {0} SELF attribute named "{1}"'.format(xmlpp_el.tag, xmlpp_self_attrib))
                #print(f"   {xmlpp_self_attrib}={xmlpp_attrib_value}")   # TODO del
                xmlpp_matches[xmlpp_matchIndex] = xmlpp_attrib_value
            xmlpp_exp = "".join(xmlpp_matches)
            #print(f'done: {xmlpp_exp}')     # TODO del

            return xmlpp_exp

        xmlpp_parent_map = {c: p for p in xmlpp_root.iter() for c in p} # https://stackoverflow.com/questions/2170610/access-elementtree-node-parent-node
        xmlpp_matches = re.split(r'(\{.*?\})', xmlpp_s)
        if (len(xmlpp_matches) <= 1):
            return False    # no {}
        if (xmlpp_DEBUG): print(f'   Evaluating: <{xmlpp_el.tag} {xmlpp_attrib_name}="{xmlpp_s}">')
        # Process all odd-numbered matches[]:
        for xmlpp_matchIndex in range(1, len(xmlpp_matches), 2):
            xmlpp_exp = xmlpp_matches[xmlpp_matchIndex][1:-1]   # [1:-1] strips { }
            xmlpp_exp = xmlpp_eval_parent(xmlpp_el, xmlpp_exp, xmlpp_attrib_name)
            try:
                xmlpp_result = eval(xmlpp_exp)
            except Exception as e:
                raise xmlpp_error(f"{type(e).__name__} evaluating {{{xmlpp_exp}}}: {sys.exception()}")
            if '{' in str(xmlpp_result): raise xmlpp_error(f"evaluated expression {xmlpp_exp} seems to contain another expression")
            #print(exp,str(result))
            xmlpp_matches[xmlpp_matchIndex] = str(xmlpp_result)
        xmlpp_matches = "".join(xmlpp_matches)
        if xmlpp_DEBUG: print(f'      Result: <{xmlpp_el.tag} {xmlpp_attrib_name}="{xmlpp_matches}"')
        return xmlpp_matches

    for xmlpp_el in xmlpp_root.iter():
        # print("tag="+el.tag)
        if (xmlpp_el.text):
            xmlpp_text = xmlpp_el.text.strip()
            if (xmlpp_text):
                # print("   tag with text: "+xmlpp_el.tag)
                xmlpp_processedText = xmlpp_evalStringWithExpressions(xmlpp_el, xmlpp_text)
                if xmlpp_processedText:
                    #print("\txmlpp_processedText=\""+xmlpp_processedText+"\"")
                    xmlpp_el.text = xmlpp_processedText
        if (xmlpp_el.tail):
            xmlpp_tail = xmlpp_el.tail.strip()
            if (xmlpp_tail):
                # print("   tag with tail: "+xmlpp_el.tag)
                xmlpp_processedText = xmlpp_evalStringWithExpressions(xmlpp_el, xmlpp_tail)
                if xmlpp_processedText:
                    #print("\txmlpp_processedText=\""+xmlpp_processedText+"\"")
                    xmlpp_el.tail = xmlpp_processedText
        xmlpp_keys = xmlpp_el.keys()
        # print("   keys=",xmlpp_keys)
        for xmlpp_key in xmlpp_keys:
            xmlpp_value = xmlpp_el.get(xmlpp_key)
            xmlpp_processedValue = xmlpp_evalStringWithExpressions(xmlpp_el, xmlpp_value, xmlpp_key)
            if xmlpp_processedValue:
                #print(f"   {xmlpp_key}")
                xmlpp_el.set(xmlpp_key, xmlpp_processedValue)

def xmlpp_remove_data_attributes():
    if (xmlpp_DEBUG): print("\nRemoving data- attributes...")
    for xmlpp_el in xmlpp_root.iter():
        for xmlpp_attrib_name in xmlpp_el.keys():
            if xmlpp_attrib_name.startswith("data-"):
                xmlpp_el.attrib.pop(xmlpp_attrib_name, None)

def xmlpp_write_dest(xmlpp_dest_file):
    xmlpp_tree.write(xmlpp_dest_file)
    if xmlpp_DEBUG: print(f"✅  {xmlpp_dest_file} written.")

def pp_log(xmlpp_arg, xmlpp_prompt="pp_log arg:"):
    # Console logging function callable from watchface-pp.xml functions and {expression}s.
    #    xmlpp_arg: value to print
    #    xmlpp_prompt: optional string to print before arg.
    # Returns xmlpp_arg.
    print(f"{xmlpp_prompt} value is '{xmlpp_arg}'; type is {type(xmlpp_arg)}")
    return xmlpp_arg

xmlpp_parse_args()
xmlpp_read_source(xmlpp_source_file)
xmlpp_exec_all_definitions()
xmlpp_extract_symbols()
xmlpp_replace_all_uses()
xmlpp_replace_all_expressions()
xmlpp_remove_data_attributes()
xmlpp_write_dest(xmlpp_dest_file)