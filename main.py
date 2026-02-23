import pandas as pd

data = {
    "task_code": ["BLK", "SHU"],
    "task_name": ["Blockwork", "Shuttering"],
    "boq": [12000, 3000],
    "rate_per_manday": [8, 6]
}

df = pd.DataFrame(data)

df["man_days"] = df["boq"] / df["rate_per_manday"]

print(df)
