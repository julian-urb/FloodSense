import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.style.use('seaborn-v0_8-whitegrid')
df = pd.read_csv('Dataset/train_set.csv')
target_map = {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Very High'}
df['risk_level'] = df['target'].map(target_map)

fig, ax = plt.subplots(figsize=(10, 6))
target_counts = df['target'].value_counts().sort_index()
colors_target = ['#27ae60', '#f39c12', '#e74c3c', '#8e44ad']
bars = ax.bar(target_counts.index, target_counts.values, color=colors_target, 
             edgecolor='#2c3e50', linewidth=2, width=0.7)
ax.set_xticks(target_counts.index)
ax.set_xticklabels([target_map[i] for i in target_counts.index], fontsize=12)
ax.set_ylabel('Count', fontsize=12)
ax.set_xlabel('Flood Risk Level', fontsize=12)
ax.set_title('Target Variable Distribution\n(Flood Risk Classification)', fontsize=14, weight='bold', pad=15)
for bar, val in zip(bars, target_counts.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15, 
            f'{val}\n({val/len(df)*100:.1f}%)', ha='center', va='bottom', fontsize=10, weight='bold')
ax.set_ylim(0, max(target_counts.values) * 1.2)
plt.tight_layout()
plt.savefig('target_distribution.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print("Saved: target_distribution.png")