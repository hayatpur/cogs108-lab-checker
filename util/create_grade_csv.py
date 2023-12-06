import argparse, json, os, sys, glob, csv
import pandas as pd
from datetime import datetime
import pytz

def main():
    VALID_ASSIGNMENTS = [
        "CL1",
        "CL2",
        "CL3",
        "CL4",
        "CL5",
        "CL6",
        "CL7",
        "CL8"
    ]

    ASSIGNMENT_NAMES = {
        "CL1": "Coding Lab 1",
        "CL2": "Coding Lab 2",
        "CL3": "Coding Lab 3",
        "CL4": "Coding Lab 4",
        "CL5": "Coding Lab 5"
    }

    parser = argparse.ArgumentParser()

    parser.add_argument("--template_file", help="The file to use as a template (download from Canvas)", required = False, default = "util/template.csv")
    parser.add_argument("--output_folder", help="The folder to write the grades to", required = False, default = None)
    parser.add_argument("--assignment_name", help="The name of the assignment", required = True, choices = VALID_ASSIGNMENTS)

    args = parser.parse_args()

    if args.output_folder is None:
        args.output_folder = f"grades/{args.assignment_name}/"

    # make the output folder if it doesn't exist
    os.makedirs(args.output_folder, exist_ok = True)

    KEY_TO_KEEP = [
        "Student",
        "ID",
        "SIS User ID",
        "SIS Login ID",
        "Section"
    ]

    # read in the template file using pandas, but only keep the keys we want
    # be sure to read in ID as a string
    template = pd.read_csv(args.template_file, dtype = {"ID": str})
    template = template[KEY_TO_KEEP]

    # Remove the row that has "206982" as the ID column
    template = template[template["ID"] != "206982"]

    # read in the input CSV files (all files starting with the assignment name inside the output folder)
    input_files = glob.glob(f"output/{args.assignment_name}*.csv")

    # read in the input files using pandas
    input_dfs = []
    for input_file in input_files:
        input_df = pd.read_csv(input_file)
        input_dfs.append(input_df)
    
    # merge the input files together
    merged_df = pd.concat(input_dfs)

    # read the deadline file
    deadline = json.load(open("util/deadlines.json"))[args.assignment_name]

    # convert the deadline to a datetime object
    deadline = datetime.strptime(deadline, "%m/%d/%Y, %I:%M%p %Z")

    # convert the deadline to PDT
    deadline = deadline.astimezone(pytz.timezone("US/Pacific"))

    # convert the date_submitted column to a datetime object
    merged_df["date_submitted"] = pd.to_datetime(merged_df["date_submitted"])

    # convert to PDT
    merged_df["date_submitted"] = merged_df["date_submitted"].dt.tz_convert("US/Pacific")

    # add a column that is true if the assignment was submitted on time
    merged_df["on_time"] = merged_df["date_submitted"] <= deadline

    # if both the column for 'effort' is 'Yes' and the column for 'on_time' is true, then the student gets full credit
    merged_df["grade"] = merged_df.apply(lambda row: 2 if row["effort"] == "Yes" and row["on_time"] else 0, axis = 1)

    # merge the template and the merged_df together (on the basis of 'student' in merged_df and 'SIS Login ID' in template)
    # when merging, keep all the rows in the template
    grade_df = pd.merge(template, merged_df, how = "left", left_on = "SIS Login ID", right_on = "student")

    # check which students in grade_df have nothing for the 'grade' column
    # these are the students that are in the template but not in the merged_df
    in_canvas_not_graded = grade_df[grade_df["grade"] != grade_df["grade"]]["SIS Login ID"]

    # check which students that were in the merged_df are not in the grade_df
    in_graded_not_canvas = set(merged_df["student"]) - set(grade_df["student"])

    # Drop any NaN in both lists
    in_canvas_not_graded = [x for x in in_canvas_not_graded if x == x]
    in_graded_not_canvas = [x for x in in_graded_not_canvas if x == x]

    # get the students that submitted late
    late_students = merged_df[merged_df["on_time"] == False]["student"]

    # get the students that did not show effort
    no_effort_students = merged_df[merged_df["effort"] == "No"]["student"]

    # write the diagnostic output to a CSV file
    grade_df.to_csv(f'{args.output_folder}/{args.assignment_name}-diagnostics.csv', index = False)

    # write a JSON of the weird students
    weird_students = {
        "in_canvas_not_graded": list(in_canvas_not_graded),
        "in_graded_not_canvas": list(in_graded_not_canvas),
        "late_students": list(late_students),
        "no_effort_students": list(no_effort_students)
    }
    json.dump(weird_students, open(f"{args.output_folder}/{args.assignment_name}-weird-students.json", "w"), indent = 4)

    # in the final CSV, keep only the columns we want (and the grade column)
    final_csv = grade_df[KEY_TO_KEEP + ["grade"]]

    # rename the grades column to the assignment name
    final_csv = final_csv.rename(columns = {"grade": ASSIGNMENT_NAMES[args.assignment_name]})

    # find the row unde the "Student" column that has "Points Possible" as a substring. Assign the cell in that row under the assignment name column to be 2. Handle NA values by skipping them
    final_csv.loc[final_csv["Student"].str.contains("Points Possible", na = False), ASSIGNMENT_NAMES[args.assignment_name]] = 2

    # write the final CSV
    final_csv.to_csv(f'{args.output_folder}/{args.assignment_name}-canvas-format.csv', index = False)

if __name__ == "__main__":
    main()