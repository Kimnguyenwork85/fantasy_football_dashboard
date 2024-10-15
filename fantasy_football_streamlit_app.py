import pandas as pd
from espn_api.football import League
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
from github import Github
import io
import json
import os
import requests

# Your league ID and current season
league_id = 1031980  # Your league ID
season_id = 2024  # Set this to the current season


# Path to store the last refresh date (could be a JSON or text file)
REFRESH_FILE = "last_refresh.json"

# Instantiate the League object outside the functions
league = League(league_id=league_id, year=season_id)

# Add a session state variable to store the last refresh date
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = None
    
# Function to load data
@st.cache_data
def load_data():
    try:
        # Read the Excel file with specified sheet names
        data = pd.read_excel("fantasy_data.xlsx", sheet_name=['Data', 'Summary'])

        # Extract DataFrames from the returned dictionary
        df = data['Data']
        summary_df = data['Summary']

        print ('df and summary type')
        print (type (df))
        print (type (summary_df))
        return df, summary_df
    except FileNotFoundError:
        return refresh_data()

    
# Function to refresh data
def refresh_data():
    weeks = []
    teams = []
    team_scores = []
    opponent_scores = []
    opponents = []
    wins = []

    for week in range(1, league.current_week):
        matchups = league.scoreboard(week=week)

        for matchup in matchups:
            home_team = matchup.home_team.team_name
            home_score = matchup.home_score
            away_team = matchup.away_team.team_name
            away_score = matchup.away_score

            # Record home team data
            weeks.append(week)
            teams.append(home_team)
            team_scores.append(home_score)
            opponent_scores.append(away_score)
            opponents.append(away_team)
            wins.append(1 if home_score > away_score else 0)

            # Record away team data
            weeks.append(week)
            teams.append(away_team)
            team_scores.append(away_score)
            opponent_scores.append(home_score)
            opponents.append(home_team)
            wins.append(1 if away_score > home_score else 0)

    df = pd.DataFrame({
        'Week': weeks,
        'Team': teams,
        'Team Score': team_scores,
        'Opponent Score': opponent_scores,
        'Opponent': opponents,
        'Win': wins
    })

    df = df[df['Team Score'] > 0].reset_index(drop=True)

    summary = {
        'Team': [],
        'Win-Loss Record': [],
        'Overall Win-Loss Record': [],
        'Mean Score': [],
        'Median Score': [],
        'Standard Deviation': [],
        'Wins': [],
        'Losses': [],
        'Winning Percentage': [],
        'Overall Wins': [],
        'Overall Losses': [],
        'Overall Winning Percentage': []
    }

    for team in df['Team'].unique():
        team_data = df[df['Team'] == team]
        
        mean_score = team_data['Team Score'].mean()
        median_score = team_data['Team Score'].median()
        std_score = team_data['Team Score'].std()

        wins_count = team_data['Win'].sum()
        losses_count = len(team_data) - wins_count

        overall_wins = 0
        overall_losses = 0
        
        for week in range(1, league.current_week + 1):
            matchups = league.scoreboard(week=week)
            for matchup in matchups:
                if matchup.home_team.team_name != team:
                    overall_wins += 1 if matchup.home_score < team_data['Team Score'].mean() else 0
                    overall_losses += 1 if matchup.home_score > team_data['Team Score'].mean() else 0

                if matchup.away_team.team_name != team:
                    overall_wins += 1 if matchup.away_score < team_data['Team Score'].mean() else 0
                    overall_losses += 1 if matchup.away_score > team_data['Team Score'].mean() else 0

        overall_win_loss_record = f"{overall_wins}-{overall_losses}"
        overall_winning_percentage = overall_wins / (overall_wins + overall_losses) if (overall_wins + overall_losses) > 0 else 0

        summary['Team'].append(team)
        summary['Win-Loss Record'].append(f"{wins_count}-{losses_count}")
        summary['Overall Win-Loss Record'].append(overall_win_loss_record)
        summary['Mean Score'].append(mean_score)
        summary['Median Score'].append(median_score)
        summary['Standard Deviation'].append(std_score)
        summary['Wins'].append(wins_count)
        summary['Losses'].append(losses_count)
        summary['Winning Percentage'].append(wins_count / len(team_data) if len(team_data) > 0 else 0)
        summary['Overall Wins'].append(overall_wins)
        summary['Overall Losses'].append(overall_losses)
        summary['Overall Winning Percentage'].append(overall_winning_percentage)

    summary_df = pd.DataFrame(summary)
    summary_df = summary_df.sort_values(by='Winning Percentage', ascending=False).reset_index(drop=True)

    save_data_to_excel(df, summary_df)

    st.session_state.last_refresh = datetime.datetime.now()

    return df, summary_df

# Function to save data to Excel
def save_data_to_excel(df, summary_df):
    with pd.ExcelWriter("fantasy_data.xlsx") as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)


# Function to read last refresh date from the file
def get_last_refresh_date():
    if os.path.exists(REFRESH_FILE):
        with open(REFRESH_FILE, "r") as file:
            data = json.load(file)
            return datetime.datetime.strptime(data['last_refresh'], "%Y-%m-%d").date()
    return None

# Function to update last refresh date in the file
def update_last_refresh_date(date):
    with open(REFRESH_FILE, "w") as file:
        json.dump({'last_refresh': date.strftime("%Y-%m-%d")}, file)

# Get today's date
today = datetime.datetime.now().date()

# Get the last refresh date from the file
last_refresh_date = get_last_refresh_date()

# Check if it's Tuesday and refresh data if needed
if datetime.datetime.now().weekday() == 1:  # 0 is Monday, 1 is Tuesday
    if last_refresh_date is None or last_refresh_date < today:
        df, summary_df = refresh_data()  # Refresh data
        update_last_refresh_date(today)  # Update the last refresh date
        save_data_to_excel(df, summary_df)  # Save the refreshed data
    else:
        df, summary_df = load_data()  # Load data without refreshing
else:
    print ('else 2')
    df, summary_df = load_data()  # Load data without refreshing

# Streamlit application
st.title("Seeking Brobromance4men Fantasy League")

# Disclaimer
st.markdown("### Disclaimer:")
st.write("The records will be refreshed every Tuesday after all week's games are completed.")
# Find the top scorer for each week
top_scorers = df.loc[df.groupby('Week')['Team Score'].idxmax()]

# Create a more aesthetically pleasing layout for the top performers
st.subheader("Top Performers Each Week")
cols = st.columns(len(top_scorers))  # Create one column per week

# Loop through each top performer and create a stylized placard
for i, row in enumerate(top_scorers.itertuples()):
    with cols[i]:
        st.metric(label=f"**Week {row.Week}**", value=f"{row.Team}", delta=f"Score: {row._3:.1f}")
        st.markdown("---")  # Adds a line for separation, making it cleaner

# Highlight Season's Best Performance
overall_top_scorer = df.loc[df['Team Score'].idxmax()]
st.subheader("Season's Best Individual Week Performance")
st.metric(label=f"**Week {overall_top_scorer.Week}**", value=f"{overall_top_scorer.Team}", delta=f"Score: {overall_top_scorer['Team Score']:.1f}")
st.markdown("---")

# Display the updated summary DataFrame
st.subheader("Overall Team Records")
st.dataframe(summary_df.style.set_table_attributes('style="width:100%;"'))

# Luck Factor = Points Scored - Opponent Points Scored
st.subheader("Box and Whisker Plot of Team Scores")
# Explanation for Box and Whisker Plot
st.write(
    """
    - The central line in each box represents the median score of each team.
    - The edges of the box indicate the first (Q1) and third quartiles (Q3), which encompass the middle 50% of the data.
    - The "whiskers" extend to show the range of scores excluding outliers.
    - Points beyond the whiskers are considered outliers.
    - This visualization allows you to quickly identify which teams have consistent scores and which ones have high variability.
    """
)
# Box and Whisker Plot
plt.figure(figsize=(10, 6))
sns.boxplot(x='Team Score', y='Team', data=df, showfliers=True)
plt.xlabel("Team Score")
plt.ylabel("Team")
plt.grid(axis='x')
st.pyplot(plt)

# Create a pivot table for the heatmap
pivot_table = df.pivot_table(index='Team', columns='Week', values='Team Score', aggfunc='mean')

st.subheader("Heatmap of Team Scores Over Weeks")
# Explanation for Heatmap
st.write(
    """
    - Each cell in the heatmap represents the average score of a team for a specific week.
    - The color intensity indicates the score level: darker shades indicate higher scores, while lighter shades show lower scores.
    - Hovering over the cells will reveal the exact score, making it easy to analyze team performance trends over time.
    - This visualization is helpful for spotting which teams consistently score well and which ones struggle"""
)
plt.figure(figsize=(12, 6))
# Use a vibrant color palette
sns.heatmap(pivot_table, annot=True, fmt=".1f", cmap="coolwarm", linewidths=.5, cbar_kws={'label': 'Score'})
plt.xlabel("Week")
plt.ylabel("Team")
st.pyplot(plt)

# Luck Factor = Points Scored - Opponent Points Scored
st.subheader("Team Luck Factor (Points Scored vs. Opponent Scores)")
st.write("The Luck Factor compares a team's points scored to their opponents' scores. A positive value indicates that a team has benefited from underperforming opponents, while a negative value suggests they faced tougher competition.")

df['Luck Factor'] = df['Team Score'] - df['Opponent Score']
luck_factor = df.groupby('Team')['Luck Factor'].sum().reset_index()

# Sort by luck factor to see who's benefited the most from low-scoring opponents
sorted_luck_df = luck_factor.sort_values(by='Luck Factor', ascending=False)

# Display luck factor as a bar chart
plt.figure(figsize=(10, 6))
sns.barplot(x='Luck Factor', y='Team', data=sorted_luck_df, palette="coolwarm")
plt.title("Luck Factor (Positive = Benefited from Opponents' Low Scores)")
plt.xlabel("Luck Factor")
plt.ylabel("Team")
st.pyplot(plt)


# Calculate the momentum for each team (difference in scores week-to-week)
st.subheader("Team Momentum (Week-to-Week Performance Changes)")
st.write("Momentum Analysis tracks how well a team performs in consecutive weeks, identifying trends in performance changes. A positive momentum value indicates improvement, while negative values show declining performance.")
df['Momentum'] = df.groupby('Team')['Team Score'].diff().fillna(0)
momentum_df = df.groupby('Team')['Momentum'].sum().reset_index()
# Visualize momentum as a bar chart
plt.figure(figsize=(10, 6))
sns.barplot(x='Momentum', y='Team', data=momentum_df.sort_values(by='Momentum', ascending=False), palette="Spectral")
plt.title("Team Momentum (Cumulative Week-to-Week Changes)")
plt.xlabel("Cumulative Momentum (Positive = Increasing Performance)")
plt.ylabel("Team")
plt.grid(True)
st.pyplot(plt)


# Strength of Schedule = Average score of opponents faced
st.subheader("Strength of Schedule (Average Opponent Score)")
st.write("This metric assesses how tough a team’s opponents have been. A higher average indicates that a team has faced more challenging opponents, providing context for win-loss records.")
df['Opponent Strength'] = df.groupby('Opponent')['Team Score'].transform('mean')
sos_df = df.groupby('Team')['Opponent Strength'].mean().reset_index()
# Visualize as a bar chart
plt.figure(figsize=(10, 6))
sns.barplot(x='Opponent Strength', y='Team', data=sos_df.sort_values(by='Opponent Strength', ascending=False), palette="mako")
plt.title("Strength of Schedule (Higher = Tougher Opponents)")
plt.xlabel("Average Opponent Score")
plt.ylabel("Team")
plt.grid(True)
st.pyplot(plt)
# Calculate Efficiency = Points per Win
st.subheader("Team Efficiency (Points per Win vs Points per Loss)")
st.write("The Efficiency Metric shows how effectively teams convert their points into wins by comparing the average points scored in wins to those in losses. A higher points-per-win ratio indicates greater efficiency.")
efficiency_df = df.groupby('Team').apply(lambda x: pd.Series({
    'Points per Win': x.loc[x['Win'] == 1, 'Team Score'].mean(),
    'Points per Loss': x.loc[x['Win'] == 0, 'Team Score'].mean()
})).reset_index()
# Plot the efficiency as a bar chart
efficiency_df = efficiency_df.melt(id_vars="Team", var_name="Metric", value_name="Score")
plt.figure(figsize=(12, 6))
sns.barplot(x='Score', y='Team', hue='Metric', data=efficiency_df, palette="Set2")
plt.title("Team Efficiency: Points per Win vs Points per Loss")
plt.xlabel("Average Points")
plt.ylabel("Team")
plt.grid(True)
st.pyplot(plt)
