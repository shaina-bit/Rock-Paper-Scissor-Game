import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional

STATS_FILE = "rps_stats.json"
DEFAULT_PLAYER_NAME = "Player"
ELO_K = 20


def clamp(n, a, b):
    return max(a, min(b, n))


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f: 
            return json.load(f)
    except Exception:
        return default


# game rules
RULESETS = {
    "RPS": {
        "moves": ["rock", "paper", "scissors"],
        "winner_map": {
            "rock": {"scissors"},
            "paper": {"rock"},
            "scissors": {"paper"},
        },
    },
    "RPSLS": {
        "moves": ["rock", "paper", "scissors", "lizard", "spock"],
        "winner_map": {
            "rock": {"scissors", "lizard"},
            "paper": {"rock", "spock"},
            "scissors": {"paper", "lizard"},
            "lizard": {"spock", "paper"},
            "spock": {"scissors", "rock"},
        },
    },
}


def decide_winner(move_a: str, move_b: str, winner_map: Dict[str, set]) -> int:
    if move_a == move_b:
        return 0
    if move_b in winner_map.get(move_a, set()):
        return 1
    return -1


class StatsManager:
    def __init__(self, path=STATS_FILE):
        self.path = path
        self.data = load_json(path, default={})
        if self.data is None:
            self.data = {}

    def get_player(self, name: str) -> dict:
        if name not in self.data:
            self.data[name] = {
                "wins": 0,
                "losses": 0,   
                "ties": 0,
                "rating": 1200,
                "total_games": 0,
                "history": [],
                "achievements": [],  
            }
        return self.data[name]

    def update_match(self, player_name: str, opponent_name: str, result: str, moves: List[Tuple[str, str]]):
        p = self.get_player(player_name)
        if result == "win":
            p["wins"] += 1
        elif result == "loss":
            p["losses"] += 1   
        elif result == "tie":
            p["ties"] += 1     
        p["total_games"] += 1
        p["history"].append({"opponent": opponent_name, "result": result, "moves": moves})
        self.save()

    def update_rating(self, player_name: str, opponent_rating: float, result_value: float):
        p = self.get_player(player_name)
        R = p["rating"]
        E = 1 / (1 + 10 ** ((opponent_rating - R) / 400))
        new_R = R + ELO_K * (result_value - E)
        p["rating"] = round(new_R)
        self.save()

    def add_achievement(self, player_name: str, achievement: str):
        p = self.get_player(player_name)
        if achievement not in p["achievements"]:  
            p["achievements"].append(achievement)
            self.save()

    def save(self):
        save_json(self.path, self.data)


# AI players
class BaseAI:
    def __init__(self, ruleset_keys="RPS"):
        self.rules = RULESETS[ruleset_keys]
        self.name = "BaseAI"

    def reset(self):
        pass

    def choose_move(self) -> str:
        raise NotImplementedError

    def observe(self, player_move: str, ai_move: str):
        pass


class RandomAI(BaseAI):
    def __init__(self, ruleset_keys="RPS"):
        super().__init__(ruleset_keys)
        self.name = "RandomAI"

    def choose_move(self) -> str:
        return random.choice(self.rules["moves"])


class FrequencyAI(BaseAI):
    def __init__(self, ruleset_keys="RPS"):
        super().__init__(ruleset_keys)
        self.name = "FrequencyAI"
        self.freq = Counter()

    def reset(self):
        self.freq = Counter()

    def observe(self, player_move: str, ai_move: str):
        self.freq[player_move] += 1

    def choose_move(self) -> str:
        if not self.freq:
            return random.choice(self.rules["moves"])
        predicted = self.freq.most_common(1)[0][0]
        counters = [m for m, beats in self.rules["winner_map"].items() if predicted in beats]
        if counters:
            return random.choice(counters)
        return random.choice(self.rules["moves"])


class MarkovAI(BaseAI):
    def __init__(self, ruleset_keys="RPS"):
        super().__init__(ruleset_keys)
        self.name = "MarkovAI"
        self.transition = defaultdict(Counter)
        self.prev = None
        self.player_freq = Counter()

    def reset(self):
        self.transition = defaultdict(Counter)
        self.prev = None
        self.player_freq = Counter()

    def observe(self, player_move: str, ai_move: str):
        if self.prev is not None:
            self.transition[self.prev][player_move] += 1
        self.prev = player_move
        self.player_freq[player_move] += 1

    def predict_next(self) -> Optional[str]:
        if self.prev and self.transition[self.prev]:
            nex, _ = self.transition[self.prev].most_common(1)[0]
            return nex
        if self.player_freq:
            return self.player_freq.most_common(1)[0][0]
        return None

    def choose_move(self) -> str:
        predicted = self.predict_next()
        if predicted:
            counters = [m for m, beats in self.rules["winner_map"].items() if predicted in beats]
            if counters:
                return random.choice(counters)
        return random.choice(self.rules["moves"])


# Player Classes
class HumanPlayer:
    def __init__(self, name=DEFAULT_PLAYER_NAME, ruleset_keys="RPS"):
        self.name = name
        self.ruleset = RULESETS[ruleset_keys]

    def choose_move(self) -> str:
        moves = self.ruleset["moves"]
        prompt = f"Choose move ({'/'.join(moves)}). Or type help or quit: "
        while True:
            choice = input(prompt).strip().lower()
            if choice == 'help':
                print(f"Moves: {', '.join(moves)}.")
                continue
            if choice in moves:
                return choice  
            if choice in ("quit", "exit"):
                raise KeyboardInterrupt
            print("Invalid move. Type 'help' for options")


# Core Game Loop
class Match:
    def __init__(self, player_name: str, ai: BaseAI, ruleset_keys="RPS", rounds=3):
        self.player_name = player_name
        self.ai = ai
        self.rules = RULESETS[ruleset_keys]
        self.rounds = rounds
        self.scores = {"player": 0, "ai": 0, "ties": 0}
        self.move_history = []

    def play_round(self, player_move: str) -> Tuple[int, str]:
        ai_move = self.ai.choose_move()
        res = decide_winner(player_move, ai_move, self.rules["winner_map"])
        if res == 1:
            self.scores["player"] += 1
            outcome = "player"
        elif res == -1:
            self.scores["ai"] += 1
            outcome = "ai"
        else:
            self.scores["ties"] += 1
            outcome = "tie"
        self.move_history.append((player_move, ai_move))
        self.ai.observe(player_move, ai_move)
        return res, ai_move

    def is_over(self) -> bool:
        needed = (self.rounds // 2) + 1
        return self.scores["player"] >= needed or self.scores["ai"] >= needed

    def result_summary(self) -> str:
        return f"{self.scores['player']} - {self.scores['ai']} (ties: {self.scores['ties']})"  # ✅ fixed quotes


# Tournament and CLI
def choose_ai(ai_key: str, ruleset_keys: str):
    ai_key = ai_key.lower()
    if ai_key == "random":
        return RandomAI(ruleset_keys)
    if ai_key == "freq":
        return FrequencyAI(ruleset_keys)
    if ai_key == "markov":
        return MarkovAI(ruleset_keys)
    raise ValueError("Unknown AI key")  


def read_int(prompt, default=None, min_val=None, max_val=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:  
            return default
        try:
            v = int(raw)
            if min_val is not None and v < min_val:
                print('Too Small')
                continue
            if max_val is not None and v > max_val:
                print('Too Big.')
                continue
            return v
        except ValueError:
            print("Enter an integer.")


def play_match_cli(stats: StatsManager, player_name: str, ruleset_key="RPS"):
    print("\n--- Start Match ---")
    print("AI types: random | freq | markov")
    ai_choice = input("Choose AI (default: markov): ").strip().lower() or "markov"
    try:
        ai = choose_ai(ai_choice, ruleset_key)
    except ValueError:
        print("Unknown AI, using Random.")
        ai = RandomAI(ruleset_key)

    rounds = read_int("Best of how many rounds? ", default=3, min_val=1)
    if rounds % 2 == 0:
        rounds += 1
        print(f"Adjusted to best-of-{rounds} (odd number required).")

    ai.reset()
    human = HumanPlayer(player_name, ruleset_key)
    match = Match(player_name, ai, ruleset_key, rounds)

    try:
        while not match.is_over():  
            print(f"\nScore: {match.result_summary()}")
            player_move = human.choose_move()   
            res, ai_move = match.play_round(player_move)

            if res == 1:
                print(f"You chose {player_move}. AI chose {ai_move} -> You win the round!")
            elif res == -1:
                print(f"You chose {player_move}. AI chose {ai_move} -> AI wins the round!")
            else:
                print(f"Both chose {player_move}. It's a tie.")
    except KeyboardInterrupt:
        print("\nMatch Aborted!")
        return

    # final result
    player_wins = match.scores["player"]
    ai_wins = match.scores["ai"]
    if player_wins > ai_wins:
        print(f"\nMATCH RESULT: YOU WIN! {player_wins} to {ai_wins}")
        result = "win"
        result_value = 1.0
    elif player_wins < ai_wins:
        print(f"\nMATCH RESULT: AI WINS. {ai_wins} to {player_wins}")
        result = "loss"
        result_value = 0.0
    else:
        print("\nMATCH RESULT: TIE.")
        result = "tie"
        result_value = 0.5

    opponent_rating = stats.get_player(ai.name)["rating"] if ai.name in stats.data else 1200
    stats.update_match(player_name, ai.name, result, match.move_history)  
    stats.update_rating(player_name, opponent_rating, result_value)

    p_stats = stats.get_player(player_name)
    if result == 'win' and p_stats['wins'] == 1:
        stats.add_achievement(player_name, "First Win")
        print("Achievement unlocked: First Win!")

    last_results = [h["result"] for h in p_stats["history"][-3:]] 
    if len(last_results) == 3 and all(r == 'win' for r in last_results):
        stats.add_achievement(player_name, "Three win streak")
        print("Achievement unlocked: Three win streak!")

    moves_only = [mv[0] for mv in match.move_history]
    if len(moves_only) >= 3 and all(m == moves_only[0] for m in moves_only):
        stats.add_achievement(player_name, "Predictable Player (Cheater?)")
        print("Note: You used the same move many times. AI may adapt accordingly.")


def show_stats(stats: StatsManager, player_name: str):
    p = stats.get_player(player_name)
    print(f"\n--- Stats for {player_name} ---")
    print(f"Wins: {p['wins']}, Losses: {p['losses']}, Ties: {p['ties']}, Total: {p['total_games']}")
    print(f"Rating: {p['rating']}")
    if p["achievements"]:
        print("Achievements:", ", ".join(p["achievements"]))
    else:
        print("Achievements: None")
    if p["history"]:
        print("Last matches (most recent first):")
        for rec in reversed(p["history"][-5:]):
            print(f"  vs {rec['opponent']}: {rec['result']} ({len(rec['moves'])} rounds)")


def main_menu():
    stats = StatsManager()
    print('Welcome to Advanced Rock-Paper-Scissors!')
    player_name = input(f"Enter your name (default: {DEFAULT_PLAYER_NAME}): ").strip() or DEFAULT_PLAYER_NAME
    while True:
        print("\nMenu:")
        print(" 1) Play match")
        print(" 2) Show my stats")
        print(" 3) Change ruleset (RPS/RPSLS)")
        print(" 4) Quick AI vs. AI demo (watch AIs play)")
        print(" 5) Reset my stats")
        print(" 0) Quit")
        choice = input("Choose an option: ").strip()
        if choice == "1":   
            ruleset_key = "RPS"
            print("Which ruleset? (1) RPS (2) RPSLS")
            r = input("Choose: ").strip()
            if r == "2":
                ruleset_key = "RPSLS"
            play_match_cli(stats, player_name, ruleset_key)
        elif choice == "2":
            show_stats(stats, player_name)
        elif choice == "3":
            print("Ruleset changed in-match only. Start a new match to apply.")
        elif choice == "4":
            print("\nAI vs AI demo: markov vs freq for 50 rounds")
            ai1 = MarkovAI("RPS")
            ai2 = FrequencyAI("RPS")
            rounds = 50
            scores = {"ai1": 0, "ai2": 0, "ties": 0}
            for i in range(rounds):
                m1 = ai1.choose_move()
                m2 = ai2.choose_move()
                res = decide_winner(m1, m2, RULESETS["RPS"]["winner_map"])
                if res == 1:
                    scores["ai1"] += 1
                elif res == -1:
                    scores["ai2"] += 1
                else:
                    scores["ties"] += 1
                ai1.observe(m2, m1)
                ai2.observe(m1, m2)
            print("Demo result:", scores)
        elif choice == "5":
            confirm = input("Are you sure you want to reset your stats? (yes/no): ").strip().lower()
            if confirm == "yes":
                stats.data[player_name] = {
                    "wins": 0, "losses": 0, "ties": 0, "rating": 1200, "total_games": 0,
                    "history": [], "achievements": []
                }
                stats.save()
                print("Stats reset.")
            else:
                print("Cancelled.")
        elif choice == "0":
            print("Goodbye — thanks for playing! Stats saved.")
            break
        else:
            print("Unknown option.")


def _test_decide_winner():
    rm = RULESETS["RPS"]["winner_map"]
    assert decide_winner("rock", "scissors", rm) == 1
    assert decide_winner("rock", "paper", rm) == -1
    assert decide_winner("paper", "paper", rm) == 0
    print("decide_winner tests passed.")


if __name__ == "__main__":
    try:
        _test_decide_winner()
    except AssertionError:
        print("Self-test failed. Exiting.")
        sys.exit(1)

    try:
        main_menu()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
