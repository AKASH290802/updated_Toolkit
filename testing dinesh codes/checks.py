import pandas as pd

# Total rows
rows = 84601

# Generate data
data = {
    'name': [f'dummy{i}' for i in range(1, rows + 1)],
    'accountnumber': [f'test{i}' for i in range(1, rows + 1)]
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to CSV
df.to_csv('dummy.csv', index=False)
