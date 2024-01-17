# Taxi

google doc for colab [here](https://docs.google.com/document/d/16MatLfGRMtWJo0qkBZWX8G26LG9UnQbqBwFqu-p9o4s/edit?usp=sharing)

## Setup

- Install `python3.12` 
- Go the the project root (this directory) in the terminal
- Run `python3.12 -m venv venv` to create a virtual environment
- Then activate the python environment using one of the commands below

| Shell      | Command to activate the environment |
| ---------- | ----------------------------------- |
| cmd        | `venv/Scripts/activate.bat`         |
| PowerShell | `venv/Scripts/Activate.ps1`         |

- Then run `pip install -r requirements.txt` to install all the requirements
- Finally, you can run `python3.12 app/main.py` to run the app

## Styling
- If you are not working with the design/styling don't worry about tailwind.
- If you don't want to use tailwind you can just add the styles inline (ie. using `<style>` tags in the html)
- If you just want to add some global styles edit the `input.css` file and not the `style.css` file and then run the command below.
- If you are working with `tailwind`; you want to start tailwind using `tailwind --input input.css --output style.css --watch --content templates/*.html` (This should be run in another terminal from the project root since it runs continuasly and updates the style.css each time an edit is made)

## Stats

```
===============================================================================
 Language            Files        Lines         Code     Comments       Blanks
===============================================================================
 CSS                     2          591          341          166           84
 HTML                    1           17           17            0            0
 Markdown                1           26            0           19            7
 Python                  1           47           35            2           10
 Plain Text              1          121            0          121            0
===============================================================================
 Total                   6          802          393          308          101
===============================================================================
```

- Don't bother updating this; I have a system to handle this automatically
- Also don't modify the on_save.sh file