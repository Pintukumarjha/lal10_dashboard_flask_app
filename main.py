'''

'''


from flask import Flask, render_template, request, redirect, session, url_for
from google.cloud import bigquery
import os
from collections import defaultdict

# Create the Flask application instance
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback_key_if_not_set')

# Set your Google service account credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service-account-key.json"

# BigQuery client
client = bigquery.Client()

# --- NEW FUNCTION TO AGGREGATE DATA ---
def aggregate_data_by_sku(raw_data):
    """
    Aggregates a list of dictionaries by 'SKU_Code', summing quantities,
    and applying a logical hierarchy to determine the final status.
    """
    # Define a status hierarchy for logical aggregation
    # Higher number means higher priority.
    status_hierarchy = {
        'Not Started': 1,
        'In-Progress': 2,
        'Completed': 3,
    }

    aggregated_data = {}

    for row in raw_data:
        sku_code = row.get('SKU_Code')
        if not sku_code:
            continue
        
        # If the SKU is not yet in our aggregated data, add it with all data
        if sku_code not in aggregated_data:
            aggregated_data[sku_code] = {
                'Style_Number': row.get('Style_Number', 'N/A'),
                'SKU_Code': sku_code,
                'Fabric_Status': row.get('Fabric_Status', 'N/A'),
                'PP_Status': row.get('PP_Status', 'N/A'),
                'Status': row.get('Status', 'N/A'),
                'Total_qty': 0,
                'Total_Unit_produced': 0
            }
        
        # --- LOGIC TO UPDATE THE STATUS BASED ON HIERARCHY ---
        current_status = aggregated_data[sku_code]['Status']
        row_status = row.get('Status')
        
        # Only update the status if the new one is more advanced.
        if row_status and status_hierarchy.get(row_status, 0) > status_hierarchy.get(current_status, 0):
            aggregated_data[sku_code]['Status'] = row_status
        
        # --- BUG FIX: Safely sum quantities by treating None as 0 ---
        # Get the quantity values, using 0 if the value is None
        total_qty = row.get('Total_qty') or 0
        total_produced = row.get('Total_Unit_produced') or 0

        # Sum the quantities
        aggregated_data[sku_code]['Total_qty'] += total_qty
        aggregated_data[sku_code]['Total_Unit_produced'] += total_produced

    # Convert the aggregated dictionary back to a list and calculate remaining quantity
    final_data = list(aggregated_data.values())
    for item in final_data:
        item['Remaining Qty'] = item['Total_qty'] - item['Total_Unit_produced']

    return final_data
# --- END OF NEW FUNCTION ---


@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        query = """
            SELECT username, Customer_Code
            FROM `lal10analytics.ERP_modules.Test_table`
            WHERE username = @username AND password = @password
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("username", "STRING", username),
                bigquery.ScalarQueryParameter("password", "STRING", password)
            ]
        )

        query_job = client.query(query, job_config=job_config)
        results = list(query_job)

        if results:
            session['username'] = username
            # Store the Buyer Name in the session
            session['Customer_Code'] = results[0]['Customer_Code']
            return redirect('/dashboard')
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    # Get the buyer name from the session instead of hardcoding
    customer_code = session.get('Customer_Code')
    if not customer_code:
        return redirect('/logout') # Redirect if buyer name is not in session
    
    # --- START OF UPDATED CODE: COMBINED QUERIES ---
    # Combine all the dashboard card count queries into a single query for efficiency.
    summary_stats_query = f"""
        SELECT
            COUNT(DISTINCT `SKU_Code`) AS total_orders,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'Completed' THEN `SKU_Code` END) AS completed_orders,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'In-Progress' THEN `SKU_Code` END) AS inprogress_orders,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'Not Started' THEN `SKU_Code` END) AS notstarted_orders,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'Completed' AND `Production_End_Status` = 'Completed & On-time' THEN `Style_Number` END) AS completed_on_time,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'Completed' AND `Production_End_Status` = 'Completed & Delay' THEN `Style_Number` END) AS completed_delay,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'In-Progress' AND `Production_End_Status` = 'In-Progress & On-time' THEN `Style_Number` END) AS inprogress_on_time,
            COUNT(DISTINCT CASE WHEN `DPR_Status` = 'In-Progress' AND `Production_End_Status` = 'In-Progress & Delayed' THEN `Style_Number` END) AS inprogress_delay
        FROM `lal10analytics.ERP_modules.no_of_styles_bpo`
        WHERE `Customer_code` = '{customer_code}'
    """

    summary_stats_job = client.query(summary_stats_query)
    
    # Check if the query returned any results
    if summary_stats_job.result() and summary_stats_job.result().total_rows > 0:
        summary_stats_result = list(summary_stats_job)[0]
    else:
        # If no results, create an empty dictionary to prevent errors
        summary_stats_result = {}

    # Unpack the results from the single query job
    total_orders = summary_stats_result.get('total_orders', 0)
    completed_orders = summary_stats_result.get('completed_orders', 0)
    inprogress_orders = summary_stats_result.get('inprogress_orders', 0)
    notstarted_orders = summary_stats_result.get('notstarted_orders', 0)
    completed_on_time = summary_stats_result.get('completed_on_time', 0)
    completed_delay = summary_stats_result.get('completed_delay', 0)
    inprogress_on_time = summary_stats_result.get('inprogress_on_time', 0)
    inprogress_delay = summary_stats_result.get('inprogress_delay', 0)
    # --- END OF UPDATED CODE ---

    # 9. Query for the Stylewise Analysis table data (This remains separate as it's a different data set)
    table_data_query = f"""
        SELECT
            `Style_Number`,
            `SKU_Code`,
            `Fabric_Status`,
            `PP_Status`,
            `DPR_Status` as `Status`,
            `Total_qty`,
            `Total_Unit_produced`
        FROM `lal10analytics.ERP_modules.no_of_styles_bpo`
        WHERE `Customer_code` = '{customer_code}'
        LIMIT 1000
    """
    table_data_job = client.query(table_data_query)
    raw_table_data = [dict(row) for row in table_data_job]
    
    # --- IMPORTANT CHANGE: AGGREGATE THE DATA BEFORE PASSING TO TEMPLATE ---
    table_data = aggregate_data_by_sku(raw_table_data)

    # --- START OF NEW CODE: CALCULATE GRAND TOTALS ---
    # This section iterates through the aggregated table data to sum the values
    # for Total_qty, Total_Unit_produced, and Remaining Qty.
    grand_totals = {
        'total_qty': sum(row.get('Total_qty', 0) for row in table_data),
        'total_unit_produced': sum(row.get('Total_Unit_produced', 0) for row in table_data),
        'remaining_qty': sum(row.get('Remaining Qty', 0) for row in table_data)
    }
    # --- END OF NEW CODE ---

    return render_template(
        "dashboard.html",
        username=session['username'],
        total_orders=total_orders,
        completed_orders=completed_orders,
        inprogress_orders=inprogress_orders,
        notstarted_orders=notstarted_orders,
        table_data=table_data, # Pass the aggregated table data to the template
        completed_on_time=completed_on_time,
        completed_delay=completed_delay,
        inprogress_on_time=inprogress_on_time,
        inprogress_delay=inprogress_delay,
        grand_totals=grand_totals # Pass the new grand totals to the template
    )
    
        

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == "__main__":
    app.run(debug=True)
