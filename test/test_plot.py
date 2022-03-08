import matplotlib.pyplot as plt
import numpy as np

from sCoda.util.util import regress


def test_plot_polynomial_function():
    terms = [
        -5.75e-015,
        2.7e+000,
        -5e+000,
        3.35e+000
    ]

    plt.rcParams["figure.figsize"] = [7.50, 3.50]
    plt.rcParams["figure.autolayout"] = True

    x = np.linspace(0, 1, 100)

    plt.plot(x, regress(x, terms), color="black", label="test")

    plt.legend(loc="upper left")

    print(regress(0, terms))
    print(regress(1, terms))

    plt.show()
