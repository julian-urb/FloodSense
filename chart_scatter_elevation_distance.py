import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use('seaborn-v0_8-whitegrid')
df = pd.read_csv('Dataset/train_set.csv')
target_map = {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Very High'}
df['risk_level'] = df['target'].map(target_map)

fig, ax = plt.subplots(figsize=(12, 8))
colors_risk = ['#27ae60', '#f39c12', '#e74c3c', '#8e44ad']
markers = ['o', 's', '^', 'D']

for i, level in enumerate([0, 1, 2, 3]):
    mask = df['target'] == level
    ax.scatter(df.loc[mask, 'elevation'], df.loc[mask, 'distance_to_river_m'], 
              c=colors_risk[i], label=target_map[level], alpha=0.65, s=35, 
              edgecolors='white', linewidth=0.3, marker=markers[i])

ax.set_xlabel('Elevation (m)', fontsize=13)
ax.set_ylabel('Distance to River (m)', fontsize=13)
ax.set_title('Elevation vs Distance to River by Flood Risk Level', fontsize=15, weight='bold', pad=15)
ax.legend(title='Risk Level', fontsize=11, title_fontsize=12, loc='upper right')
ax.set_yscale('log')
ax.axhline(y=10, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Riverbank')
ax.axvline(x=10, color='blue', linestyle='--', linewidth=1, alpha=0.5, label='Lowland threshold')
ax.text(12, 8, 'Very High Risk Zone\n(Lowland + River proximity)', fontsize=9, color='#e74c3c', style='italic')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('scatter_elevation_vs_distance.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("Saved: scatter_elevation_vs_distance.png")