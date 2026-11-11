"""Build Table 1, Table 2 and one figure from results/raw/results.jsonl."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_json("results/raw/results.jsonl", lines=True)
df = df[df.stage.isin(["S0", "S2"])]
Path("results/tables").mkdir(parents=True, exist_ok=True)

t1 = (df[df.stage == "S2"].groupby("condition")
      .agg(accuracy=("correct", "mean"), mean_steps=("steps_n", "mean"),
           mean_latency_s=("latency_s", "mean"), runs=("correct", "size")).round(3))
t1.to_csv("results/tables/table1_accuracy_by_condition.csv")

t2 = df.pivot_table(index="condition", columns="stage", values="correct", aggfunc="mean")
t2["delta"] = t2["S2"] - t2["S0"]
steps = df.pivot_table(index="condition", columns="stage", values="steps_n", aggfunc="mean")
t2["steps_S0"], t2["steps_S2"] = steps["S0"], steps["S2"]
t2 = t2.round(3)
t2.to_csv("results/tables/table2_S0_vs_S2.csv")

print("Table 1 (held-out, stage S2)\n", t1, "\n")
print("Table 2 (S0 vs S2)\n", t2)

ax = t2[["S0", "S2"]].plot(kind="bar", ylim=(0, 1.05), rot=0)
ax.set_ylabel("Held-out accuracy")
ax.set_title("Accuracy before (S0) and after (S2) experience")
plt.tight_layout()
plt.savefig("results/tables/fig_s0_vs_s2.png", dpi=200)