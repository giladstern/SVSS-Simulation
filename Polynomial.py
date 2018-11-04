from random import randint


class Polynomial:
    def __init__(self, coefficients):
        self.coef = coefficients
        self.minimize()
        self.deg = len(self.coef) - 1

    def __add__(self, other):
        if self.deg >= other.deg:
            res = self.coef[:]
            oth = other.coef
        else:
            res = other.coef[:]
            oth = self.coef

        for i, val in enumerate(oth):
            res[i] += val

        return Polynomial(res)

    def __mul__(self, other):
        deg = self.deg + other.deg
        coefficients = [0] * (deg + 1)
        for i, v in enumerate(self.coef):
            for j, u in enumerate(other.coef):
                coefficients[i+j] += u * v

        return Polynomial(coefficients)

    def cmult(self, c):
        for i in range(len(self.coef)):
            self.coef[i] *= c
        return self

    def eval(self, x):
        power = 1
        total = 0

        for c in self.coef:
            total += power * c
            power *= x

        return total

    def minimize(self):

        while len(self.coef) > 1 and self.coef[-1] == 0:
            self.coef.pop()

    @staticmethod
    def interpolate(vals):
        total = Polynomial([0])

        for i in range(len(vals)):
            total += Polynomial.lagrange_basis(vals, i).cmult(vals[i][1])

        # This is one solution, this becomes worse the more elements we have
        res = [round(c) for c in total.coef]

        return Polynomial(res)

    @staticmethod
    def lagrange_basis(vals,index):
        total = Polynomial([1])
        for i in range(len(vals)):
            if i != index:
                p = Polynomial([-vals[i][0],1])
                p.cmult(1/(vals[index][0] - vals[i][0]))
                total *= p

        return total

    @staticmethod
    def random_polynomial(secret, deg, field):
        coef = [secret]
        for i in range(deg):
            coef.append(randint(0, field))

        return Polynomial(coef)

    def __repr__(self):
        return str(self.coef)

    def __str__(self):
        return str(self.coef)

    def __eq__(self, other):
        return self.coef == other.coef


class BivariatePolynomial:
    def __init__(self, coefficients):
        self.coef = coefficients
        self.minimize()
        self.x_deg = len(self.coef) - 1
        self.y_deg = max(len(c) for c in self.coef) - 1

    def minimize(self):
        res = [Polynomial(poly).coef for poly in self.coef]
        while len(res) > 1 and res[-1] == [0]:
            res.pop()
        self.coef = res

    def __add__(self, other):
        x_max_ind = max(self.x_deg, other.x_deg) + 1
        y_max_ind = max(self.y_deg, other.y_deg) + 1

        res = [[0] * (y_max_ind) for i in range(x_max_ind)]

        for i in range(x_max_ind):
            for j in range(y_max_ind):
                if len(self.coef) > i and len(self.coef[i]) > j:
                    res[i][j] += self.coef[i][j]
                if len(other.coef) > i and len(other.coef[i]) > j:
                    res[i][j] += other.coef[i][j]

        return BivariatePolynomial(res)

    def __mul__(self, other):
        x_deg = self.x_deg + other.x_deg
        y_deg = self.y_deg + other.y_deg
        coefficients = [[0] * (y_deg + 1) for i in range(x_deg+1)]

        for x1 in range(len(self.coef)):
            for y1 in range(len(self.coef[x1])):
                for x2 in range(len(other.coef)):
                    for y2 in range(len(other.coef[x2])):
                        coefficients[x1 + x2][y1 + y2] += self.coef[x1][y1] * other.coef[x2][y2]

        return BivariatePolynomial(coefficients)

    def cmult(self, c):
        for i in range(len(self.coef)):
            for j in range(len(self.coef[i])):
                self.coef[i][j] *= c
        return self

    def eval(self, x, y):
        x_power = 1
        total = 0

        for coef in self.coef:
            p = Polynomial(coef)
            total += x_power * p.eval(y)
            x_power *= x

        return total

    @staticmethod
    def random_polynomial(secret, deg, field):
        coef = []
        for i in range(deg + 1):
            univariate_coef = []
            for j in range(deg + 1):
                univariate_coef.append(randint(0, field))
            coef.append(univariate_coef)
        coef[0][0] = secret

        return BivariatePolynomial(coef)

    def __repr__(self):
        return str(self.coef)

    def __str__(self):
        return str(self.coef)

    def __eq__(self, other):
        return self.coef == other.coef

    def g(self, j):
        coef = [0] * (self.y_deg + 1)
        pow = 1

        for c in self.coef:
            for i in range(len(c)):
                coef[i] += c[i] * pow
            pow *= j

        return Polynomial(coef)

    def h(self, j):
        coef = [0] * (self.x_deg + 1)

        for i in range(len(self.coef)):
            pow = 1
            c = self.coef[i]
            for k in range(len(c)):
                coef[i] += c[k] * pow
                pow *= j

        return Polynomial(coef)
