# ============================================================
# MANPOWER FORECASTING SYSTEM — FULL FINAL CODE (GLOBAL WORKING DAYS)
# ============================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.figure_factory as ff

st.set_page_config(
    page_title="Manpower Forecasting System",
    page_icon="👷‍♂️",
    layout="wide"
)

# ------------------------------------------------------------
# Load master data
# ------------------------------------------------------------
trade_master = pd.read_csv("data/trade_master.csv")
task_master = pd.read_csv("data/task_master.csv")

# ------------------------------------------------------------
# Helper: Calculate baseline man-days & manpower
# ------------------------------------------------------------
def calculate_baseline(rate, boq, start_date, end_date):
    man_days = boq / rate
    duration_days = (end_date - start_date).days + 1
    manpower = man_days / duration_days
    return man_days, manpower, duration_days

# Weekday mapping
weekday_map = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6
}

# ============================================================
# SECTION 1 — INPUT SYSTEM
# ============================================================

st.title("Manpower Forecasting System")

st.subheader("Select Tasks")

task_list = task_master["task_code"].tolist()
selected_tasks = st.multiselect("Choose one or more tasks:", task_list)

if not selected_tasks:
    st.stop()

selected_df = task_master[task_master["task_code"].isin(selected_tasks)]
selected_df = selected_df.merge(trade_master, on="trade_id", how="left")

# ------------------------------------------------------------
# GLOBAL WORKING DAY SELECTOR
# ------------------------------------------------------------
st.subheader("Select Working Days for All Tasks")

default_working_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

global_working_days = st.multiselect(
    "Working Days (Global)",
    options=list(weekday_map.keys()),
    default=default_working_days
)

selected_weekdays = [weekday_map[d] for d in global_working_days]

# ------------------------------------------------------------
# TASK INPUT TABLE
# ------------------------------------------------------------
st.subheader("Enter BOQ, Dates, and Rate")

editable_df = selected_df[[
    "task_code", "task_name", "rate_per_manday", "uom", "trade_name"
]].copy()

editable_df["BOQ"] = 0.0
editable_df["Start Date"] = datetime.today().date()
editable_df["End Date"] = datetime.today().date()

edited_df = st.data_editor(
    editable_df,
    num_rows="dynamic",
    column_config={
        "task_code": st.column_config.TextColumn("Task Code", disabled=True),
        "task_name": st.column_config.TextColumn("Task Name", disabled=True),
        "rate_per_manday": st.column_config.NumberColumn("Rate per Manday"),
        "uom": st.column_config.TextColumn("UOM", disabled=True),
        "trade_name": st.column_config.TextColumn("Trade", disabled=True),
        "BOQ": st.column_config.NumberColumn("BOQ", min_value=1.0),
        "Start Date": st.column_config.DateColumn("Start Date"),
        "End Date": st.column_config.DateColumn("End Date")
    }
)

# ------------------------------------------------------------
# GENERATE BASELINE
# ------------------------------------------------------------
if st.button("Generate Initial Report"):

    baseline_results = []

    for _, row in edited_df.iterrows():

        boq = row["BOQ"]
        start_date = row["Start Date"]
        end_date = row["End Date"]

        if boq <= 0:
            st.error(f"BOQ must be > 0 for task {row['task_code']}")
            st.stop()

        if end_date < start_date:
            st.error(f"End date cannot be before start date for task {row['task_code']}")
            st.stop()

        man_days, manpower, duration = calculate_baseline(
            row["rate_per_manday"], boq, start_date, end_date
        )

        baseline_results.append({
            "task_code": row["task_code"],
            "task_name": row["task_name"],
            "trade_name": row["trade_name"],
            "boq": boq,
            "rate": row["rate_per_manday"],
            "man_days": man_days,
            "duration_days": duration,
            "manpower": manpower,
            "start_date": start_date,
            "end_date": end_date
        })

    baseline_df = pd.DataFrame(baseline_results)

    st.success("Initial Report Generated")

    st.write("### Baseline Task Forecast")
    st.dataframe(baseline_df)

    st.session_state["baseline_df"] = baseline_df
    st.session_state["working_days"] = selected_weekdays

    # Trade-wise baseline summary
    trade_summary = baseline_df.groupby("trade_name")["manpower"].sum().reset_index()

    st.write("### Baseline Trade-wise Manpower Summary")
    st.dataframe(trade_summary)

    st.write("### Baseline Manpower Histogram (Baseline)")
    st.bar_chart(trade_summary.set_index("trade_name"))

    # Baseline daily curve (true manpower per day)
    st.write("### Baseline Manpower Curve (Daily)")
    timeline_rows = []
    for _, row in baseline_df.iterrows():
        dates = pd.date_range(row["start_date"], row["end_date"])
        daily_mp = row["manpower"]  # already man-days / duration_days
        for d in dates:
            timeline_rows.append({
                "date": d,
                "trade_name": row["trade_name"],
                "manpower": daily_mp
            })

    timeline_df = pd.DataFrame(timeline_rows)
    pivot_df = timeline_df.pivot(index="date", columns="trade_name", values="manpower").fillna(0)
    st.line_chart(pivot_df)


# ============================================================
# SECTION 2 — PROGRESS ADJUSTMENT
# ============================================================

if "baseline_df" in st.session_state:

    baseline_df = st.session_state["baseline_df"]
    selected_weekdays = st.session_state["working_days"]

    st.subheader("Progress Adjustment")

    # ------------------------------------------------------------
    # TASK-WISE PROGRESS (MASTER FOR MANPOWER)
    # ------------------------------------------------------------
    st.write("### Task-wise Progress Adjustment")

    task_progress_df = baseline_df[[
        "task_code", "task_name", "man_days", "duration_days", "boq"
    ]].copy()

    task_progress_df["Planned Manpower"] = (
            task_progress_df["man_days"] / task_progress_df["duration_days"]
    ).round(2)

    # Task-wise progress still used for manpower
    task_progress_df["Progress %"] = 100.0

    task_progress_df["Adjusted Man-Days"] = (
            task_progress_df["man_days"] / (task_progress_df["Progress %"] / 100)
    )

    task_progress_df["Adjusted Manpower"] = (
            task_progress_df["Adjusted Man-Days"] / task_progress_df["duration_days"]
    ).round(2)

    # Initial Balance BOQ (will be overwritten later by daily/weekly logic)
    task_progress_df["Balance BOQ"] = (
            task_progress_df["boq"] * (1 - task_progress_df["Progress %"] / 100)
    )

    task_progress_df = st.data_editor(
        task_progress_df,
        column_config={
            "task_code": st.column_config.TextColumn("Task Code", disabled=True),
            "task_name": st.column_config.TextColumn("Task Name", disabled=True),
            "man_days": st.column_config.NumberColumn("Planned Man-Days", disabled=True),
            "duration_days": st.column_config.NumberColumn("Duration (Days)", disabled=True),
            "boq": st.column_config.NumberColumn("BOQ", disabled=True),
            "Planned Manpower": st.column_config.NumberColumn("Planned MP", disabled=True),
            "Progress %": st.column_config.NumberColumn("Progress %", min_value=1.0, max_value=300.0),
            "Adjusted Man-Days": st.column_config.NumberColumn("Adjusted Man-Days", disabled=True),
            "Adjusted Manpower": st.column_config.NumberColumn("Adjusted MP", disabled=True),
            "Balance BOQ": st.column_config.NumberColumn("Balance BOQ", disabled=True),
        }
    )

    # Recalculate after edits (still for manpower only)
    task_progress_df["Progress %"] = task_progress_df["Progress %"].astype(float)

    task_progress_df["Adjusted Man-Days"] = (
            task_progress_df["man_days"] / (task_progress_df["Progress %"] / 100)
    )

    task_progress_df["Adjusted Manpower"] = (
            task_progress_df["Adjusted Man-Days"] / task_progress_df["duration_days"]
    ).round(2)

    # This Balance BOQ will be replaced later using daily/weekly progress
    task_progress_df["Balance BOQ"] = (
            task_progress_df["boq"] * (1 - task_progress_df["Progress %"] / 100)
    )

    st.session_state["task_progress_df"] = task_progress_df

    # ------------------------------------------------------------
    # WEEKLY PROGRESS (AUTO-DIVIDED)
    # ------------------------------------------------------------
    st.write("### Weekly Progress Adjustment")

    with st.expander("Show Weekly Progress Table"):

        weekly_rows = []

        for _, row in baseline_df.iterrows():

            dates = pd.date_range(row["start_date"], row["end_date"])
            working_days = [d for d in dates if d.weekday() in selected_weekdays]

            weeks = {}
            for d in working_days:
                week_key = d.isocalendar().week
                if week_key not in weeks:
                    weeks[week_key] = []
                weeks[week_key].append(d)

            num_weeks = len(weeks)
            weekly_percent = round(100.0 / num_weeks, 2) if num_weeks > 0 else 0.0

            for week_key, days in weeks.items():
                weekly_rows.append({
                    "Task": row["task_code"],
                    "Week Start": min(days),
                    "Week End": max(days),
                    "Working Days": len(days),
                    "Progress %": weekly_percent
                })

        weekly_df = pd.DataFrame(weekly_rows)
        weekly_df["Week Start"] = pd.to_datetime(weekly_df["Week Start"])
        weekly_df["Week End"] = pd.to_datetime(weekly_df["Week End"])

        weekly_df = st.data_editor(
            weekly_df,
            column_config={
                "Task": st.column_config.TextColumn("Task", disabled=True),
                "Week Start": st.column_config.DateColumn("Week Start", disabled=True),
                "Week End": st.column_config.DateColumn("Week End", disabled=True),
                "Working Days": st.column_config.NumberColumn("Working Days", disabled=True),
                "Progress %": st.column_config.NumberColumn("Progress %", min_value=0.0, max_value=300.0)
            }
        )

        st.session_state["weekly_df"] = weekly_df

    # ------------------------------------------------------------
    # DAILY PROGRESS (AUTO-DIVIDED)
    # ------------------------------------------------------------
    st.write("### Daily Progress Adjustment")

    with st.expander("Show Daily Progress Table"):

        daily_rows = []

        for _, row in baseline_df.iterrows():

            dates = pd.date_range(row["start_date"], row["end_date"])
            working_days = [d for d in dates if d.weekday() in selected_weekdays]

            if len(working_days) > 0:
                daily_percent = round(100.0 / len(working_days), 2)
            else:
                daily_percent = 0.0

            for d in dates:
                p = daily_percent if d in working_days else 0.0
                daily_rows.append({
                    "Task": row["task_code"],
                    "Date": d,
                    "Progress %": p
                })

        daily_df = pd.DataFrame(daily_rows)
        daily_df["Date"] = pd.to_datetime(daily_df["Date"])

        daily_df = st.data_editor(
            daily_df,
            column_config={
                "Task": st.column_config.TextColumn("Task", disabled=True),
                "Date": st.column_config.DateColumn("Date", disabled=True),
                "Progress %": st.column_config.NumberColumn("Progress %", min_value=0.0, max_value=300.0)
            }
        )

        st.session_state["daily_df"] = daily_df

    # ------------------------------------------------------------
    # REPORT TYPE SELECTION
    # ------------------------------------------------------------
    st.subheader("Select Final Report Type")

    report_type = st.radio(
        "Choose report type:",
        ["Daily Report", "Weekly Report"]
    )

    if st.button("Generate Final Report"):
        st.session_state["generate_final"] = True
        st.session_state["report_type"] = report_type

# ============================================================
# SECTION 3 — FINAL REPORT
# ============================================================

if st.session_state.get("generate_final", False):

    st.subheader("Final Adjusted Report")

    baseline_df = st.session_state["baseline_df"]
    task_progress_df = st.session_state["task_progress_df"]
    weekly_df = st.session_state["weekly_df"]
    daily_df = st.session_state["daily_df"]
    report_type = st.session_state["report_type"]
    selected_weekdays = st.session_state["working_days"]

    weekly_df["Week Start"] = pd.to_datetime(weekly_df["Week Start"])
    weekly_df["Week End"] = pd.to_datetime(weekly_df["Week End"])
    daily_df["Date"] = pd.to_datetime(daily_df["Date"])

    merged = baseline_df.merge(
        task_progress_df[["task_code", "Adjusted Man-Days"]],
        on="task_code",
        how="left"
    )

    adjusted_rows = []

    for _, row in merged.iterrows():

        dates = pd.date_range(row["start_date"], row["end_date"])
        duration = len(dates)
        base_mp = row["Adjusted Man-Days"] / duration

        for d in dates:
            adjusted_rows.append({
                "Task": row["task_code"],
                "Trade": row["trade_name"],
                "Date": d,
                "Manpower": base_mp
            })

    adjusted_df = pd.DataFrame(adjusted_rows)

    # ------------------------------------------------------------
    # APPLY ONLY THE SELECTED REFINEMENT
    # ------------------------------------------------------------
    if report_type == "Weekly Report":

        # WEEKLY REFINEMENT ONLY (correct proportional logic)
        for _, w in weekly_df.iterrows():

            mask = (
                    (adjusted_df["Task"] == w["Task"]) &
                    (adjusted_df["Date"] >= w["Week Start"]) &
                    (adjusted_df["Date"] <= w["Week End"])
            )

            # Planned weekly progress for this task
            task_row = baseline_df[baseline_df["task_code"] == w["Task"]].iloc[0]
            dates = pd.date_range(task_row["start_date"], task_row["end_date"])
            working_days = [x for x in dates if x.weekday() in selected_weekdays]

            weeks = {}
            for d in working_days:
                wk = d.isocalendar().week
                if wk not in weeks:
                    weeks[wk] = []
                weeks[wk].append(d)

            planned_weekly = 100 / len(weeks) if len(weeks) > 0 else 0
            actual_weekly = w["Progress %"]

            if planned_weekly > 0:
                factor = actual_weekly / planned_weekly
                adjusted_df.loc[mask, "Manpower"] *= factor

    elif report_type == "Daily Report":

        # DAILY REFINEMENT ONLY (correct proportional logic)
        for _, d in daily_df.iterrows():

            mask = (
                    (adjusted_df["Task"] == d["Task"]) &
                    (adjusted_df["Date"] == d["Date"])
            )

            # Planned daily progress for this task
            task_row = baseline_df[baseline_df["task_code"] == d["Task"]].iloc[0]
            dates = pd.date_range(task_row["start_date"], task_row["end_date"])
            working_days = [x for x in dates if x.weekday() in selected_weekdays]

            planned_daily = 100 / len(working_days) if len(working_days) > 0 else 0
            actual_daily = d["Progress %"]

            if planned_daily > 0:
                factor = actual_daily / planned_daily
                adjusted_df.loc[mask, "Manpower"] *= factor

    # ------------------------------------------------------------
    # PER-TASK PROPORTIONAL SCALING
    # ------------------------------------------------------------
    for task in adjusted_df["Task"].unique():

        task_df = adjusted_df[adjusted_df["Task"] == task]
        actual_total = task_df["Manpower"].sum()

        required_total = float(
            task_progress_df.loc[
                task_progress_df["task_code"] == task, "Adjusted Man-Days"
            ].iloc[0]
        )

        scale = required_total / actual_total if actual_total > 0 else 1.0

        adjusted_df.loc[adjusted_df["Task"] == task, "Manpower"] *= scale

    adjusted_df["Manpower"] = adjusted_df["Manpower"].round(2)

    # ------------------------------------------------------------
    # EFFECTIVE PROGRESS & BALANCE BOQ
    # ------------------------------------------------------------

    if report_type == "Daily Report":
        # DAILY EFFECTIVE PROGRESS
        effective_progress = (
            daily_df.groupby("Task")["Progress %"].sum().reset_index()
        )
        effective_progress.columns = ["task_code", "Effective Progress %"]

        # Error if daily sum > 100%
        for _, row in effective_progress.iterrows():
            if row["Effective Progress %"] > 100:
                st.error(
                    f"Daily progress for task {row['task_code']} exceeds 100%. "
                    f"Current total = {row['Effective Progress %']}%."
                )
                st.stop()

        # Merge into task_progress_df
        task_progress_df = task_progress_df.merge(
            effective_progress,
            on="task_code",
            how="left"
        )

        # Balance BOQ based on daily effective progress
        task_progress_df["Balance BOQ"] = (
                task_progress_df["boq"] * (1 - task_progress_df["Effective Progress %"] / 100)
        )

    elif report_type == "Weekly Report":
        # WEEKLY EFFECTIVE PROGRESS
        weekly_eff = weekly_df.groupby("Task")["Progress %"].sum().reset_index()
        weekly_eff.columns = ["task_code", "Weekly Effective Progress %"]

        # Merge into task_progress_df
        task_progress_df = task_progress_df.merge(
            weekly_eff,
            on="task_code",
            how="left"
        )

        # Balance BOQ based on weekly effective progress
        task_progress_df["Balance BOQ"] = (
                task_progress_df["boq"] * (1 - task_progress_df["Weekly Effective Progress %"] / 100)
        )

    # ------------------------------------------------------------
    # FINAL OUTPUTS
    # ------------------------------------------------------------
    if report_type == "Daily Report":
        st.write("### Final Adjusted Manpower Curve (Daily)")
        pivot_final = adjusted_df.pivot(index="Date", columns="Trade", values="Manpower").fillna(0)
        st.line_chart(pivot_final)

    elif report_type == "Weekly Report":
        st.write("### Final Adjusted Manpower Curve (Weekly)")
        adjusted_df["Week"] = adjusted_df["Date"].dt.isocalendar().week
        weekly_curve = adjusted_df.groupby(["Week", "Trade"])["Manpower"].mean().reset_index()
        pivot_week = weekly_curve.pivot(index="Week", columns="Trade", values="Manpower").fillna(0)
        st.line_chart(pivot_week)

    st.write("### Final Trade-wise Manpower Summary")
    trade_final = adjusted_df.groupby("Trade")["Manpower"].mean().reset_index()
    trade_final.rename(columns={"Manpower": "Average Manpower"}, inplace=True)

    st.write("### Final Trade-wise Manpower Summary (Average Manpower)")
    st.dataframe(trade_final)

    st.write("### Final Manpower Histogram (Adjusted, Average per Day)")
    st.bar_chart(trade_final.set_index("Trade"))

    st.write("### Final Task Summary")
    if report_type == "Daily Report":
        final_task_summary = task_progress_df[[
            "task_code", "man_days", "Planned Manpower",
            "Effective Progress %", "Adjusted Man-Days",
            "Adjusted Manpower", "Balance BOQ"
        ]]
    else:
        final_task_summary = task_progress_df[[
            "task_code", "man_days", "Planned Manpower",
            "Weekly Effective Progress %", "Adjusted Man-Days",
            "Adjusted Manpower", "Balance BOQ"
        ]]
    st.dataframe(final_task_summary)

    with st.expander("Show Gantt Chart"):
        gantt_data = []
        for _, row in baseline_df.iterrows():
            gantt_data.append(dict(
                Task=row["task_code"],
                Start=row["start_date"],
                Finish=row["end_date"]
            ))
        fig = ff.create_gantt(gantt_data, index_col="Task", show_colorbar=True, group_tasks=True)
        st.plotly_chart(fig, use_container_width=True)

    st.success("Final Report Generated Successfully")
