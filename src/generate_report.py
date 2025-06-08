from datetime import datetime, date
from pathlib import Path
import pandas as pd
import plotly.express as px
from settings import CLIENT_QUOTAS, HOLIDAY_FILE


def generate_report():
    df = pd.read_csv("sessions.csv", parse_dates=["Start", "End"])
    df["Duration"] = (df["End"] - df["Start"]).dt.total_seconds() / 3600
    df["Date"] = df["Start"].dt.date
    df["Week"] = df["Start"].dt.to_period("W").apply(lambda r: r.start_time)
    df["Month"] = df["Start"].dt.to_period("M").apply(lambda r: r.start_time)
    df["Weekday"] = df["Start"].dt.weekday

    chart_height = 500

    # ----- Plot 1: Daily totals -----
    per_day = df.groupby(["Client", "Date"])["Duration"].sum().reset_index()
    fig_day = px.bar(
        per_day,
        x="Date",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Day",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- Plot 2: Weekly totals -----
    weekly = df.groupby(["Client", "Week"])["Duration"].sum().reset_index()
    fig_weekly = px.bar(
        weekly,
        x="Week",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Week",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- Plot 3: Monthly totals -----
    monthly = df.groupby(["Client", "Month"])["Duration"].sum().reset_index()
    fig_monthly = px.bar(
        monthly,
        x="Month",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Month",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- Plot 4: Average per Day -----
    days_worked = df.groupby("Client")["Date"].nunique()
    total_hours = df.groupby("Client")["Duration"].sum()
    daily_avg = (total_hours / days_worked).reset_index()
    daily_avg.columns = ["Client", "AvgHoursPerDay"]
    fig_avg = px.bar(
        daily_avg,
        x="Client",
        y="AvgHoursPerDay",
        title="Average Hours per Day (All Days)",
        labels={"AvgHoursPerDay": "Avg Hours"},
        height=chart_height,
    )

    # ----- Quota Summary -----
    def progress_bar(actual, target):
        percent = min(100, (actual / target) * 100 if target > 0 else 0)
        color = "#dc3545"  # red
        if percent >= 100:
            color = "#28a745"  # green
        elif percent >= 80:
            color = "#ffc107"  # yellow

        return f"""
        <div style="margin:12px 0;  padding:0 8px;">
            <div style="font-size:13px; margin-bottom:2px;">{actual:.1f}h of {target:.1f}h</div>
            <div style="background:#333; border-radius:6px; height:14px; width:100%;">
                <div style="width:{percent:.1f}%; background:{color}; height:100%; border-radius:6px;"></div>
            </div>
        </div>
        """

    def expected_hours(start_date, end_date, client):
        quota_cfg = CLIENT_QUOTAS.get(client.lower())
        if not quota_cfg:
            return 0

        weekly_quota = quota_cfg["weekly_schedule"]
        workdays = pd.bdate_range(start=start_date, end=end_date).to_series().dt.date

        holidays = set()
        holidays_path = Path(HOLIDAY_FILE)
        if holidays_path.exists():
            with open(holidays_path) as f:
                holidays = {
                    datetime.strptime(line.strip().split()[0], "%Y-%m-%d").date()
                    for line in f
                    if line.strip() and not line.startswith("#")
                }

        total = 0.0
        for day in workdays:
            if day in holidays:
                continue
            weekday = day.weekday()
            if weekday in weekly_quota:
                total += weekly_quota[weekday]

        return total

    def actual_hours(df, from_date):
        return df[df["Start"] >= pd.Timestamp(from_date)]["Duration"].sum()

    # Compute quota summary for "sandisk"
    quota_html = ""
    sandisk_df = df[df["Client"].str.lower() == "sandisk"]
    if not sandisk_df.empty:
        today = pd.Timestamp.now().normalize()
        start_of_week = today - pd.Timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        # --- End of week: latest business day up to today ---
        week_range = pd.bdate_range(start=start_of_week, end=today)
        end_of_week = week_range[-1].date() if len(week_range) else today.date()

        # --- End of month: latest business day up to today ---
        month_range = pd.bdate_range(start=start_of_month, end=today)
        end_of_month = month_range[-1].date() if len(month_range) else today.date()

        # Compute expected and actual
        today_hours = sandisk_df[sandisk_df["Date"] == today.date()]["Duration"].sum()
        week_hours = actual_hours(sandisk_df, start_of_week)
        month_hours = actual_hours(sandisk_df, start_of_month)

        week_expected = expected_hours(start_of_week, end_of_week, "sandisk")
        month_expected = expected_hours(start_of_month, end_of_month, "sandisk")

        quota_html = f"""
        <hr>
        <div style='font-family:sans-serif;'>
        <div class='summary-title'>Summary (Sandisk)</div>

        <b>Today:</b> {today_hours - 8:+.1f}h 
        {progress_bar(today_hours, 8)}

        <b>This Week:</b> {week_hours - week_expected:+.1f}h 
        {progress_bar(week_hours, week_expected)}

        <b>This Month:</b> {month_hours - month_expected:+.1f}h 
        {progress_bar(month_hours, month_expected)}
        </div>
        <hr>
        <p>.</p>
        """

    # ----- Combine HTML report -----
    html_path = Path("report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(
            "<html><head><title>Time Tracking Report</title>"
            "<style>"
            ".main-wrap {"
            "  max-width: 1000px;"
            "  margin: 32px auto;"
            "  background: #23272e;"
            "  color: #f5f6fa;"
            "  border-radius: 12px;"
            "  box-shadow: 0 2px 16px #0003;"
            "  padding: 32px 32px 24px 32px;"
            "  font-family: 'Segoe UI', sans-serif;"
            "}"
            ".summary-title {padding: 2em 0;}"
            "body { background: #181a20; }"
            "h3 { margin-top: 0; }"
            "</style>"
            "</head><body><div class='main-wrap'>\n"
        )
        f.write("<h3 style='font-family:sans-serif;'>Time Tracking Summary</h3>\n")
        f.write(quota_html)
        f.write(fig_day.to_html(full_html=False, include_plotlyjs="cdn"))
        f.write(fig_weekly.to_html(full_html=False, include_plotlyjs=False))
        f.write(fig_monthly.to_html(full_html=False, include_plotlyjs=False))
        f.write(fig_avg.to_html(full_html=False, include_plotlyjs=False))
        f.write("</body></div></html>")

    print(f"✅ Report saved to {html_path.resolve()}")
