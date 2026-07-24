import pandas as pd

df = pd.read_csv("dataset/train.csv")

df["label"] = df.apply(
    lambda row:
    "bullying"
    if (
        row["toxic"] == 1
        or row["severe_toxic"] == 1
        or row["obscene"] == 1
        or row["threat"] == 1
        or row["insult"] == 1
        or row["identity_hate"] == 1
    )
    else "non-bullying",
    axis=1
)

new_df = df[["comment_text", "label"]]

new_df.columns = ["text", "label"]

new_df.to_csv(
    "dataset/bullying_dataset.csv",
    index=False
)

print("Dataset prepared successfully")
print(new_df.head())