# Setup

Install packages:
```
pip install flask
pip install nbdime
```

Pull in the latest student submissions: (Do this everytime)

```
scp -r grader-cogs108-02@dsmlp-login.ucsd.edu:/dsmlp/workspaces-fs04/COGS108_SP24_A00/home/grader-cogs108-02/submitted ./labs
```

Start the grader:

```
python basic-flask.py --lab="CL1"
```

> [!NOTE]
> It only works on Firefox, it's easiest to set it as your default browser while grading.

# Credits
Forked from Samuel Taylor's grader for Cogs 18: https://github.com/0xSMT/cogs18-lab-checker