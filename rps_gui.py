import tkinter as tk
from tkinter import messagebox
from advanced_rps_game import Match, HumanPlayer, RandomAI, FrequencyAI, MarkovAI, StatsManager, RULESETS

stats = StatsManager()
player_name = "Player"
ruleset_key = "RPS"

# Creating the main GUI window
root = tk.Tk()
root.title("Rock Paper Scissors")
root.geometry("400x400")

# Adding Labels to show game info
score_label = tk.Label(root, text="Score: You 0 - AI 0 (Ties: 0)", font=("Arial", 14))
score_label.pack(pady=10)

ai_move_label = tk.Label(root, text="AI Move: ?", font=("Arial", 12))
ai_move_label.pack(pady=5)

result_label = tk.Label(root, text="", font=("Arial", 12))
result_label.pack(pady=5)

# Setup AI and Match
ai = MarkovAI(ruleset_key)
ai.reset()
match = Match(player_name, ai, ruleset_key, rounds=3)

# Create Button callbacks for moves
def play_move(player_move):
    res, ai_move = match.play_round(player_move)
    ai_move_label.config(text=f"AI Move: {ai_move}")

    if res == 1:
        result_label.config(text="You win this round!")
    elif res == -1:
        result_label.config(text="AI wins this round!")
    else:
        result_label.config(text="This round is a tie!")

    # Update the score label here after every round
    score_label.config(
        text=f"Score: You {match.scores['player']} - AI {match.scores['ai']} (Ties: {match.scores['ties']})"
    )

    # Check if match is over after each move
    if match.is_over():
        if match.scores['player'] > match.scores['ai']:
            messagebox.showinfo("Match Over", f"You won the match! {match.result_summary()}")
        elif match.scores['player'] < match.scores['ai']:
            messagebox.showinfo("Match Over", f"AI won the match! {match.result_summary()}")
        else:
            messagebox.showinfo("Match Over", f"It's a tie! {match.result_summary()}")
        root.quit()  # end of GUI after match

# Create Buttons for Player Moves
button_frame = tk.Frame(root)
button_frame.pack(pady=20)

for move in RULESETS[ruleset_key]["moves"]:
    btn = tk.Button(button_frame, text=move.capitalize(), width=10,
                    command=lambda m=move: play_move(m))
    btn.pack(side="left", padx=5)

root.mainloop()
