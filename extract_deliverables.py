"""
How to use this table generator.

This script parses the LSST DESC Science Roadmap latex files into a 
comma-separated value list that you can paste into a confluence page.

To use it:
1. Run the command: python extract_deliverables filename1.tex filename2.tex ...
   for all the latex files you want table rows for. 

2. Copy the result to clipboard.  On Macs there is a shortcut for these steps:
    python extract_deliverables filename1.tex | pbcopy 

2. In confluence, go to the page you want to add the table to, click "Edit"
   and then the "+" symbol (insert more content) at the top.  
   Select "{} Markup" from the dropdown menu.

3. Paste into the box in the window that opens, then click "Insert".

4. You may need to edit to remove latex markup.  You can also change the 
   status boxes by clicking on the colored "Waiting" box to change the 
   color and text if the item is complete or late.

Joe Zuntz

"""

import glob
import re
import pyparsing as pp
import collections
import sys
import csv

def parse_projects(text):
    #the list which will contain the located projects
    projects = []

    #this enables parsing something with nested brackets 
    #just finding the outermost thing
    SB = pp.nestedExpr(opener='[', closer=']')
    RB = pp.nestedExpr(opener='{', closer='}')

    #The latex patterns we are looking for.
    project_pattern = r"\keyproject" + SB + RB + RB
    deliverable_pattern = r"\deliverable" + SB + RB + RB
    keytask_pattern = r"\keytask" + SB + RB + RB
    prereq_pattern = r"\prereq" + pp.nestedExpr(opener='{', closer='}')
# \prereq{\deliverableref{TJP2-DC1-SW1}, \deliverableref{CI5}}


    #tell each pattern to append to the project list when
    #a project is found. Because we pass the same list object 
    #to all of them they can all read/write from/to the same one
    project_pattern.setParseAction(ProjectParser(projects))
    deliverable_pattern.setParseAction(DeliverableParser(projects))
    keytask_pattern.setParseAction(KeyTaskParser(projects))
    prereq_pattern.setParseAction(PreReqParser(projects))

    #the overall search pattern is to look for any of the
    #three patterns defined above
    search_pattern = pp.Or([project_pattern, deliverable_pattern, keytask_pattern, 
        prereq_pattern])

    #scan the text.
    #we have to use a loop because otherwise it returns a lazy generator
    #that doesn't actually start work
    for _ in search_pattern.scanString(text):
        pass

    #return our list of projects
    return projects

class ElementParser(object):
    def __init__(self, projects):
        self.projects = projects

    def parse(self, content):
        # All the elements we are parsing here have the same
        #signature, fortunately.
        code = match_to_string(content[1])
        date = match_to_string(content[2])
        name = match_to_string(content[3])
        info = {}
        info['name'] = name
        info['code'] = code
        info['date'] = date

        return info

class ProjectParser(ElementParser):
    def __call__(self, s, loc, content):
        info = self.parse(content)
        info['deliverables'] = []
        self.projects.append(info)

class DeliverableParser(ElementParser):
    def __call__(self, s, loc, content):
        info = self.parse(content)
        info['keytasks'] = []
        info['prereqs'] = []
        current_project = self.projects[-1]
        current_project['deliverables'].append(info)

class KeyTaskParser(ElementParser):
    def __call__(self, s, loc, content):
        info = self.parse(content)
        current_project = self.projects[-1]
        current_deliverable = current_project['deliverables'][-1]
        current_deliverable['keytasks'].append(info)

class PreReqParser(object):
    def __init__(self, projects):
        self.projects = projects
        RB = pp.nestedExpr(opener='{', closer='}')
        self.projectref_pattern = r"\keyprojectref" + RB
        self.deliverableref_pattern = r"\deliverableref" + RB

    def __call__(self, s, loc, content):
        content = content.asList()
        content = content[1]
        # print '-'*30
        # print content
        # print '-'*30
        if not content:
            return

        current_project = self.projects[-1]
        current_deliverable = current_project['deliverables'][-1]
        prereqs = current_deliverable['prereqs']

        i = 0
        while True:
            # print content[i], type(content[i])
            if isinstance(content[i], str) and content[i].strip(',').strip()==r'\deliverableref':
                for req in content[i+1]:
                    if req==',': continue
                    prereqs.append('deliverable:'+req)
                i+=2
            elif isinstance(content[i], str) and content[i].strip(',').strip()==r'\keyprojectref':
                for req in content[i+1]:
                    if req==',': continue
                    prereqs.append('keyproject:'+req)
                i+=2
            else:
                i+=1
            if i>=len(content):
                break
        # print
        # print "project {0} reqs:{1}".format(current_project['name'], prereqs)
        # print
        # print

def find_included_files(base):
    #find all files that have been \include'd in our base file
    include = re.compile(r'\\include\{([a-zA-z0-9]+)\}', re.VERBOSE|re.MULTILINE)
    text = read_latex(base)
    return include.findall(text)


def read_latex(filename):
    #read a file and remove latex-commented lines
    text = '\n'.join(line for line in open(filename).readlines() if not line.strip().startswith('%'))
    return text

def match_to_string(m):
    #flatten a list of matches into a space-separated string.
    if isinstance(m, str):
        return m
    return ' '.join(match_to_string(mi) for mi in m)


def dump_projects(groups):
    for filename, projects in groups.items():
        if not projects: continue
        print filename.upper()
        print "="*max(len(filename), 10)
        print
        for proj in projects:
            print "+ {0[name]}  [{0[code]}]".format(proj)
            for dv in proj['deliverables']:
                print '    -  {0[name]}  [{0[code]}]'.format(dv)
                for kt in dv['keytasks']:
                    print '        + {0[name]}  [{0[code]}]'.format(kt)
            print
        print
        print
        print


def extract_all():
    #find all the files included in the base "srm.tex" file
    filenames = find_included_files("srm.tex")
    groups = {}
    for filename in filenames:
        text = read_latex(filename+".tex")
        projects = parse_projects(text)
        if projects:
            groups[filename] = projects

    # dump_projects(groups)

    #Some other possible outputs:
    import json
    print json.dumps(groups)

    # import yaml
    # print yaml.dump(groups)
    

def generate_confluence_table(filenames):
    projects = []
    for filename in filenames:
        group_name = filename[:-4].upper()
        text = read_latex(filename)
        projects += parse_projects(text)
    header = ["Key Task","Due date","Description","People working on this","Existing / completed work","Status"]
    print  "||" + ("||".join(header)) + "||"
    # print "{csv:macros=true|columns=Task, Date, Description, People, Work, Status|augments=,,,%Status%,}"
    
    # writer = csv.writer(sys.stdout)
    # writer.writerow(header)
    

    for project_index, project in enumerate(projects):
        project_index += 1
        
        for deliverable_index, deliverable in enumerate(project['deliverables']):
            deliverable_index+=1
            for task_index, task in enumerate(deliverable['keytasks']):
                task_index += 1
                code = "{0}{1}.{2}.{3}".format(group_name, project_index, deliverable_index, task_index)
                status = "{status:colour=Gray|title=Waiting}"
                # writer.writerow([code, task['date'], task['name'], " ", " ", status])
                row = [code, task['date'], task['name'], " ", " ", status]
                print "|"+ "|".join(row) + "|"
    print "{csv}"

if __name__ == '__main__':
    if len(sys.argv)==1:
        print __doc__
    else:
        generate_confluence_table(sys.argv[1:])