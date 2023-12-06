import argparse, json, os, sys, glob, runpy, csv
from flask import Flask, render_template, session, redirect, url_for, send_file, request

import multiprocessing

import webbrowser
from threading import Timer

app = Flask(__name__)

MEMORY = {}

def run_diff(original_notebook_path, student_notebook_path):
    try:
        sys.argv = ['nbdime.webapp.nbdiffweb', original_notebook_path, student_notebook_path, '--show-unchanged']
        runpy.run_module('nbdime.webapp.nbdiffweb', run_name='__main__')
    except SystemExit:
        # write a temporary file to indicate that the diff is finished
        with open('.temp.diff.finished', 'w') as f:
            f.write('')


@app.route('/')
def index():
    global MEMORY

    if MEMORY['current_student_index'] >= len(MEMORY['student_names']):
        return redirect(url_for('finished'))
    else:
        student = MEMORY['student_names'][MEMORY['current_student_index']]

        student_grade_status = {}
        # extract a dictionary of the student ID's mapped to whether or not they have been graded
        for student_id in MEMORY['student_names']:
            # get student grade if it exists
            student_grade = None
            for row in MEMORY['output']:
                if row['student'] == student_id:
                    if row['effort'] == 'Yes':
                        student_grade = "good"
                    elif row['effort'] == 'No':
                        student_grade = "bad"
                    else:
                        student_grade = "ungraded"
                    break
            
            student_grade_status[student_id] = student_grade
        
        return render_template('index.html', student=student, students = student_grade_status)

@app.route('/show_diff')
def show_diff():
    global MEMORY
    
    student = MEMORY['student_names'][MEMORY['current_student_index']]    

    p = multiprocessing.Process(target=run_diff, args=(MEMORY['original_notebook_path'], MEMORY['students'][student]))
    p.start()

    return render_template('show_diff.html', student=student)

@app.route('/grade_student')
def grade_student():
    global MEMORY

    student = MEMORY['student_names'][MEMORY['current_student_index']]

    return render_template('grade_student.html', student=student)

@app.route('/next_file')
def next_file():
    global MEMORY

    if MEMORY['current_student_index'] < len(MEMORY['student_names']) - 1:
        MEMORY['current_student_index'] += 1
    else:
        return redirect(url_for('finished'))

    return redirect(url_for('index'))

@app.route('/yes_effort')
def yes_effort():
    global MEMORY

    # check if the student ID is already in the output
    student_id = MEMORY['student_names'][MEMORY['current_student_index']]

    # if the student ID is already in the output, then update the effort grade
    for row in MEMORY['output']:
        if row['student'] == student_id:
            row['effort'] = 'Yes'
            break

    # write in-progress csv
    with open(MEMORY['output_path'], 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['student', 'lab', 'effort', 'date_submitted'])
        writer.writeheader()
        writer.writerows(MEMORY['output'])

    # go to the the /next route once finished
    return redirect(url_for('next_file'))

@app.route('/no_effort')
def no_effort():
    global MEMORY

    # check if the student ID is already in the output
    student_id = MEMORY['student_names'][MEMORY['current_student_index']]

    # if the student ID is already in the output, then update the effort grade
    for row in MEMORY['output']:
        if row['student'] == student_id:
            row['effort'] = 'No'
            break

    # write in-progress csv
    with open(MEMORY['output_path'], 'w') as f:
        writer = csv.DictWriter(f, fieldnames=['student', 'lab', 'effort', 'date_submitted'])
        writer.writeheader()
        writer.writerows(MEMORY['output'])

    # go to the the /next route once finished
    return redirect(url_for('next_file'))

@app.route('/is_done')
def is_done():
    # check if the diff is done
    if os.path.exists('.temp.diff.finished'):
        os.remove('.temp.diff.finished')
        
        # return json indicating that the diff is done
        return json.dumps({'done': True})
    else:
        # do nothing
        return json.dumps({'done': False})

@app.route('/finished')
def finished():
    # render template and kill server
    return render_template('finished.html')

@app.route('/download')
def download():
    global MEMORY

    # return the csv file
    return send_file(MEMORY['output_path'], as_attachment=True)

# create a route that goes to a specific student ID
@app.route('/go_to_<student>')
def go_to_student(student):
    global MEMORY

    # find the index of the student
    MEMORY['current_student_index'] = MEMORY['student_names'].index(student)

    # go to the index page
    return redirect(url_for('index'))


def main():
    global MEMORY

    # parse command line arguments
    parser = argparse.ArgumentParser()

    STUDENT_NOTEBOOKS_ROOT = "labs/submitted"

    STUDENT_NOTEBOOK_PATTERNS = {
        "CL1": "Coding Lab 1/CL1-Tooling.ipynb",
        "CL2": "Coding-Lab-2/CL2-ProgrammingI.ipynb",
        "CL3": "Coding-Lab-3/CL3-Programming.ipynb",
        "CL4": "Coding-Lab-4/CL4-Collections.ipynb",
        "CL5": "Coding-Lab-5/CL5-Loops.ipynb",
        "CL6": "Coding-Lab-6/CL6-Classes.ipynb",
        "CL7": "Coding-Lab-7/CL7-CommandLine.ipynb",
        "CL8": "Coding-Lab-8/CL8-ScientificComputing.ipynb"
    }

    ASSIGNMENT_NOTEBOOK_PATH = {
        "CL1": "labs/assignments/CL1-Tooling.ipynb",
        "CL2": "labs/assignments/CL2-ProgrammingI.ipynb",
        "CL3": "labs/assignments/CL3-Programming.ipynb",
        "CL4": "labs/assignments/CL4-Collections.ipynb",
        "CL5": "labs/assignments/CL5-Loops.ipynb",
        "CL6": "labs/assignments/CL6-Classes.ipynb",
        "CL7": "labs/assignments/CL7-CommandLine.ipynb",
        "CL8": "labs/assignments/CL8-ScientificComputing.ipynb"
    }

    parser.add_argument("--lab", help="The lab to be graded", choices=STUDENT_NOTEBOOK_PATTERNS.keys())
    # add flags for --evens and --odds (cannot pass both)
    parser.add_argument('--evens', help='Whether to grade only even students', action='store_true')
    parser.add_argument('--odds', help='Whether to grade only odd students', action='store_true')
    
    args = parser.parse_args()

    if args.evens and args.odds:
        print("Cannot pass both --evens and --odds")
        sys.exit(1)

    original_notebook_path = ASSIGNMENT_NOTEBOOK_PATH[args.lab]
    
    # load in the original notebook as JSON
    with open(original_notebook_path) as f:
        MEMORY['original_notebook_path'] = original_notebook_path
        MEMORY['original_notebook']  = json.load(f)

    student_notebooks_path = STUDENT_NOTEBOOKS_ROOT
    
    # get all the paths of the student notebooks
    student_names = glob.glob(student_notebooks_path + "/*")
    student_names = [os.path.basename(s) for s in student_names]

    # only keep the student IDs where they have submitted the lab
    student_names = [s for s in student_names if os.path.exists(student_notebooks_path + "/" + s + "/" + STUDENT_NOTEBOOK_PATTERNS[args.lab])]

    MEMORY['student_names'] = sorted(student_names)
    MEMORY['current_student_index'] = 0 

    if args.evens:
        MEMORY['student_names'] = MEMORY['student_names'][::2]
    elif args.odds:
        MEMORY['student_names'] = MEMORY['student_names'][1::2]

    MEMORY['students'] = {}

    # create a dictionary of student names to their notebook paths
    for student in student_names:
        MEMORY['students'][student] = student_notebooks_path + "/" + student + "/" + STUDENT_NOTEBOOK_PATTERNS[args.lab]

    # construct a dictionary for the final csv. should have columns for student name, date submitted, and effort grade
    MEMORY['output'] = []
    for student in MEMORY['student_names']:
        timestamp_path = MEMORY['students'][student].replace(os.path.basename(MEMORY['students'][student]), 'timestamp.txt')
        with open(timestamp_path) as f:
            date_submitted = f.read().strip()

        MEMORY['output'].append({
            'student': student,
            'lab': args.lab,
            'effort': None,
            'date_submitted': date_submitted,
        })

    if args.evens:
        suffix = 'evens'
    elif args.odds:
        suffix = 'odds'
    else:
        suffix = 'all'

    MEMORY['output_path'] = f'./output/{args.lab}-grades-{suffix}.csv'

    # if the output file doesn't exist, then create it
    if not os.path.exists(MEMORY['output_path']):
        with open(MEMORY['output_path'], 'w') as f:
            writer = csv.DictWriter(f, fieldnames=['student', 'lab', 'effort', 'date_submitted'])
            writer.writeheader()
            writer.writerows(MEMORY['output'])

    # only do first 3 students
    # MEMORY['student_names'] = MEMORY['student_names'][:3]

    # look at the output csv and see which students have already been graded
    # update the students in MEMORY['student_names'] with those that have been graded
    if os.path.exists(MEMORY['output_path']):
        with open(MEMORY['output_path']) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # get the index of the student in MEMORY['student_names']
                student_name = row['student']
                
                # update the student's effort grade
                for student in MEMORY['output']:
                    if student['student'] == student_name:
                        student['effort'] = row['effort']
                        break

    # set the current student index to the first student that hasn't been graded yet
    for student in MEMORY['student_names']:
        # find the row in the output csv that corresponds to the student
        for row in MEMORY['output']:
            if row['student'] == student:
                # if the student hasn't been graded yet, then set the current student index to that student
                if row['effort'] == None or row['effort'] == '':
                    MEMORY['current_student_index'] = MEMORY['student_names'].index(row['student'])
                    return


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    main()
    # Timer(1, open_browser).start()
    app.run(debug=True)