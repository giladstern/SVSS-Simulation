from random import randrange
from Message import Message


class RandomOrderSimulator:
    """
    This simulator only simulates a random order.
    It does not simulate RB's correctly, seeing as they can be sent with less than n-t participants,
    as well as having all RB's received at the same time by all processors.
    """
    def __init__(self):
        self.waiting = []
        self.players = {}
        self.reconstruct_started = {}
        self.inner_time = 0

    def send(self, message, to):
        self.waiting.append((message, to))

    def RB(self, message):
        self.waiting.append((message, None))

    def step(self):
        message, to = self.waiting.pop(randrange(len(self.waiting)))

        if to:
            self.players[to].DMM(message)
        else:
            for player in self.players.values():
                player.DMM(message)

        self.inner_time += 1

    def remaining(self):
        return len(self.waiting) > 0

    def time(self):
        return self.inner_time


class Simulator(RandomOrderSimulator):
    """
    This simulator simulates RB faithfully as well as having a random order.
    It doesn't actually have the full RB protocol, but checks if n-t senders are willing to participate,
    and if n-t are willing to participate with them.
    In order to be a more faithful simulation, this needs to be done t+1 times.
    If there are enough senders that are willing to work with each other, each sender receives a copy eventually.
    """
    def __init__(self, n, t):
        super().__init__()
        self.waiting_RB = []
        self.n = n
        self.t = t

    def RB(self, message):
        self.waiting_RB.append(message)

    def step(self):
        self.retry_RB()
        super().step()

    def retry_RB(self):
        to_add = []
        for message in self.waiting_RB:
            counter = 0
            for player in self.players.values():
                if not player.delay_message(message, message.tag):
                    player_message = Message(None, message.tag, player.id, None, None, True)
                    player_counter = 0
                    for second_player in self.players.values():
                        if not second_player.delay_message(player_message, message.tag):
                            player_counter += 1
                    if player_counter >= self.n - self.t:
                        counter += 1
            if counter >= self.n - self.t:
                to_add.append(message)
        self.waiting_RB = [message for message in self.waiting_RB if message not in to_add]
        for message in to_add:
            for player in self.players:
                self.waiting.append((message, player))

    def remaining(self):
        if super().remaining():
            return True
        self.retry_RB()
        return super().remaining()
