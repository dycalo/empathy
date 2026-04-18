import re

with open("empathy/cli/main.py") as f:
    content = f.read()

import_statement = "from empathy.cli.config import app as config_app\n"
add_typer = 'app.add_typer(config_app, name="config", help="Manage user prototypes and skills")\n'

# Add import at the top
content = re.sub(
    r"(from empathy\.core\.models import DialogueMeta, Speaker\n)",
    r"\1" + import_statement,
    content,
)

# Add add_typer call before the @app.callback()
content = re.sub(
    r"(_STATUS_COLOR: dict\[str, str\] = {[^}]+}\n\n)", r"\1" + add_typer + "\n", content
)

with open("empathy/cli/main.py", "w") as f:
    f.write(content)
