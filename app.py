import streamlit as st
import boto3
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(page_title="QuickSight Dashboard Permissions", layout="wide")

st.title("📊 QuickSight Dashboard Access Audit")

# Inputs
account_id = st.text_input("AWS Account ID")
region = st.selectbox("AWS Region", ["us-east-1", "us-west-2", "eu-west-1"])

@st.cache_resource
def get_client(region):
    return boto3.client("quicksight", region_name=region)


# -----------------------------
# Permissions Logic
# -----------------------------
def get_dashboard_permissions(client, account_id, dashboard_id):
    try:
        response = client.describe_dashboard_permissions(
            AwsAccountId=account_id,
            DashboardId=dashboard_id
        )

        permissions = response.get("Permissions", [])
        principals = [p["Principal"] for p in permissions]

        # Detect "Enable access for Everyone in this account" toggle.
        # When that toggle is ON, QuickSight adds a namespace-level principal:
        #   arn:aws:quicksight:<region>:<account-id>:namespace/<namespace>
        # That principal has no "user/" or "group/" segment — it IS the namespace itself.
        import re
        _namespace_arn = re.compile(
            r"arn:aws:quicksight:[^:]+:\d+:namespace/\S+", re.IGNORECASE
        )

        def _is_everyone(principal: str) -> bool:
            # Primary signal: namespace-level ARN (the "Everyone in this account" toggle)
            if _namespace_arn.fullmatch(principal.strip()):
                return True
            # Secondary signal: group explicitly named for broad access
            if "/group/" in principal.lower():
                group_name = principal.lower().split("/group/")[-1].split("/")[-1]
                return group_name in {"everyone", "all", "allusers", "all-users", "all_users"}
            return False

        is_open = any(_is_everyone(p) for p in principals)

        return principals, "Yes" if is_open else "No"

    except Exception as e:
        return [f"Error: {str(e)}"], "Unknown"


# -----------------------------
# Last Published Time (activity proxy)
# -----------------------------
def get_last_published(client, account_id, dashboard_id):
    """
    describe_dashboard returns LastPublishedTime which reflects the last time
    a version was published — a reliable proxy for whether the dashboard is
    actively maintained / in use.
    """
    try:
        response = client.describe_dashboard(
            AwsAccountId=account_id,
            DashboardId=dashboard_id
        )
        ts = response.get("Dashboard", {}).get("LastPublishedTime")
        return ts
    except Exception:
        return None


# -----------------------------
# Fetch Dashboards
# -----------------------------
def list_dashboards_with_permissions(client, account_id):
    dashboards = []
    next_token = None
    now = datetime.now(timezone.utc)

    while True:
        params = {"AwsAccountId": account_id}
        if next_token:
            params["NextToken"] = next_token

        response = client.list_dashboards(**params)

        for d in response.get("DashboardSummaryList", []):
            dashboard_id = d["DashboardId"]

            principals, open_flag = get_dashboard_permissions(
                client, account_id, dashboard_id
            )

            last_published = get_last_published(client, account_id, dashboard_id)

            # Days since last publish — lower = more recently active
            if last_published:
                delta = now - last_published.replace(tzinfo=timezone.utc) \
                    if last_published.tzinfo is None \
                    else now - last_published
                days_since_published = delta.days
            else:
                days_since_published = None

            dashboards.append({
                "Dashboard Name": d["Name"],
                "Dashboard ID": dashboard_id,
                "Shared With Everyone": open_flag,
                "# Principals": len([p for p in principals if not p.startswith("Error")]),
                "Last Published": last_published,
                "Days Since Published": days_since_published,
                "Last Updated": d.get("LastUpdatedTime"),
                "Created Time": d.get("CreatedTime"),
                "Principals": ", ".join(principals),
            })

        next_token = response.get("NextToken")
        if not next_token:
            break

    return dashboards


# -----------------------------
# UI Action
# -----------------------------
if st.button("Scan Dashboards"):
    if not account_id:
        st.error("Please enter AWS Account ID")
    else:
        client = get_client(region)

        with st.spinner("Scanning dashboards and permissions..."):
            data = list_dashboards_with_permissions(client, account_id)

            if data:
                df = pd.DataFrame(data)

                # Format timestamps
                for col in ["Last Published", "Last Updated", "Created Time"]:
                    df[col] = pd.to_datetime(df[col], errors="coerce", utc=True) \
                                .dt.strftime("%Y-%m-%d %H:%M UTC")

                # Sort by most recently published first (actively used at top)
                df = df.sort_values("Days Since Published", ascending=True, na_position="last")

                st.session_state["dashboard_df"] = df
            else:
                st.session_state.pop("dashboard_df", None)
                st.warning("No dashboards found.")

# Render results + filters whenever we have cached data
if "dashboard_df" in st.session_state:
    df = st.session_state["dashboard_df"]

    st.success(f"Found {len(df)} dashboards")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        show_open_only = st.checkbox("Show only 'Shared With Everyone' dashboards")
    with col2:
        active_days = st.number_input(
            "Show dashboards published within N days (0 = show all)",
            min_value=0, value=0, step=30
        )

    filtered = df.copy()
    if show_open_only:
        filtered = filtered[filtered["Shared With Everyone"] == "Yes"]
    if active_days > 0:
        filtered = filtered[
            filtered["Days Since Published"].notna() &
            (filtered["Days Since Published"] <= active_days)
        ]

    # Summary metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Dashboards", len(df))
    m2.metric("Shared With Everyone", (df["Shared With Everyone"] == "Yes").sum())
    m3.metric(
        "Active (last 90 days)",
        int(df["Days Since Published"].le(90).sum())
    )

    st.dataframe(filtered, width='stretch')

    # Download
    st.download_button(
        "Download CSV",
        filtered.to_csv(index=False),
        "dashboard_permissions_audit.csv",
        "text/csv"
    )