from flask import Flask, request, jsonify
from flask_cors import CORS
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

TABLE_SCHEMA = {
    "users": ["id", "name", "email", "created_at"],
    "orders": ["id", "user_id", "total", "created_at"]
}

COLUMN_TO_TABLE = {
    col: table
    for table, cols in TABLE_SCHEMA.items()
    for col in cols
}

OPERATORS = {
    "greater than": ">",
    "less than": "<",
    "equals": "=",
    "not equals": "!=",
    "contains": "LIKE",
    "starts with": "LIKE",
    "ends with": "LIKE",
    "greater than or equals": ">=",
    "less than or equals": "<=",
    "between": "BETWEEN"
}

def parse_select_columns(user_input):
    print(f"Parsing select columns from: {user_input}")
    select_columns = []
    select_match = re.search(r"select\s+(.+?)(?:\s+where|$)", user_input, re.IGNORECASE)
    if select_match:
        columns = [col.strip() for col in select_match.group(1).split("and")]
        for col in columns:
            col = col.strip()
            if col in COLUMN_TO_TABLE:
                table = COLUMN_TO_TABLE[col]
                select_columns.append(f"{table}.{col}")
    return select_columns

def parse_where_conditions(user_input):
    print(f"Parsing where conditions from: {user_input}")
    where_conditions = []
    where_match = re.search(r"where\s+(.+)$", user_input, re.IGNORECASE)
    
    if where_match:
        conditions = where_match.group(1).split(" and ")
        for condition in conditions:
            if handle_between_operator(condition, where_conditions):
                continue
            handle_other_operators(condition, where_conditions)
    
    return where_conditions

def handle_between_operator(condition, where_conditions):
    between_match = re.search(r"(\w+)\s+between\s+(\S+)\s+and\s+(\S+)", condition.strip(), re.IGNORECASE)
    if between_match:
        col, value1, value2 = between_match.groups()
        if col in COLUMN_TO_TABLE:
            table = COLUMN_TO_TABLE[col]
            where_conditions.append(f"{table}.{col} BETWEEN '{value1}' AND '{value2}'")
        return True
    return False

def handle_other_operators(condition, where_conditions):
    for operator_text, operator_symbol in OPERATORS.items():
        pattern = rf"(\w+)\s+{operator_text}\s+(.+?)(?:\s+and|$)"
        match = re.search(pattern, condition.strip(), re.IGNORECASE)
        if match:
            col, value = match.groups()
            value = value.strip().strip("'\"")
            
            if col in COLUMN_TO_TABLE:
                table = COLUMN_TO_TABLE[col]
                
                # Handle special values
                value = handle_special_values(value)
                
                # Handle LIKE operators
                if operator_symbol == "LIKE":
                    value = handle_like_operators(operator_text, value)
                else:
                    value = f"'{value}'"
                
                where_conditions.append(f"{table}.{col} {operator_symbol} {value}")
                break

def handle_special_values(value):
    if value.lower() == "today":
        return datetime.now().strftime('%Y-%m-%d')
    elif value.lower() == "this month":
        return datetime.now().strftime('%Y-%m')
    return value

def handle_like_operators(operator_text, value):
    if operator_text == "contains":
        return f"'%{value}%'"
    elif operator_text == "starts with":
        return f"'{value}%'"
    elif operator_text == "ends with":
        return f"'%{value}'"
    return value

def determine_required_tables(select_columns, where_conditions):
    tables = set()
    # Add tables from selected columns
    for col in select_columns:
        tables.add(col.split('.')[0])
    # Add tables from where conditions
    for condition in where_conditions:
        table = condition.split('.')[0]
        tables.add(table)
    return list(tables)

@app.route('/generate_sql', methods=['POST'])
def generate_sql():
    data = request.json
    user_input = data.get("query", "").lower()
    print(f"Processing query: {user_input}")

    select_columns = parse_select_columns(user_input)
    where_conditions = parse_where_conditions(user_input)
    
    # Determine required tables and construct FROM clause
    tables = determine_required_tables(select_columns, where_conditions)
    primary_table = "orders" if "orders" in tables else "users"
    
    # Generate SQL query
    select_clause = ", ".join(select_columns) if select_columns else "*"
    from_clause = f" FROM {primary_table}"
    
    # Add JOIN clause if needed
    join_clause = ""
    if "users" in tables and "orders" in tables:
        if primary_table == "orders":
            join_clause = " JOIN users ON users.id = orders.user_id"
        else:
            join_clause = " JOIN orders ON users.id = orders.user_id"
    
    where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    sql = f"SELECT {select_clause}{from_clause}{join_clause}{where_clause};"
    print(f"Generated SQL: {sql}")
    
    return jsonify({"sql_query": sql})

if __name__ == "__main__":
    app.run(debug=True)
