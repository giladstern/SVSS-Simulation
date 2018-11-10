from random import randrange


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
    It doesn't actually have the full RB protocol, but checks if n-t senders are willing to participate.
    If there are enough senders, each sender receives a copy of the message at some future time.
    Technically, in order to truly simulate RB, n - t isn't enough.
    We need n - t out of which enough processors listen to each other.
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
