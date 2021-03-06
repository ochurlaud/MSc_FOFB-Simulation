# -*- coding: utf-8 -*-

from __future__ import division, print_function

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
import sympy as sy


def poly_to_sympy(num, den, symbol='s', simplify=True):
    """ Convert Scipy's LTI instance to Sympy expression """
    s = sy.Symbol(symbol)
    G = sy.Poly(num, s) / sy.Poly(den, s)
    return sy.simplify(G) if simplify else G


def poly_from_sympy(xpr, symbol='s'):
    """ Convert Sympy transfer function polynomial to Scipy LTI """
    s = sy.Symbol(symbol)
    num, den = sy.simplify(xpr).as_numer_denom()  # expressions
    p_num_den = sy.poly(num, s), sy.poly(den, s)  # polynomials
    c_num_den = [sy.expand(p).all_coeffs() for p in p_num_den]  # coefficients

    # convert to floats
    l_num, l_den = [sy.lambdify((), c)() for c in c_num_den]
    return l_num, l_den


def TF_from_signal(y, u, fs, method='correlation', plot=False, plottitle=''):
    if len(y.shape) == 1:
        y = y.reshape((1, y.size))
    M, N = y.shape

    H_all = np.zeros((M, int(N/2)), dtype=complex)
    fr = np.fft.fftfreq(N, 1/fs)[:int(N/2)]

    if method == "correlation":
        a = signal.correlate(u, u, "same")
    else:
        a = u

    if plot:
        plt.figure()
    for k in range(M):
        if method == "correlation":
            c = signal.correlate(y[k, :], u, "same")
        else:
            c = y[k, :]

        A = np.fft.fft(a)
        idx = np.where(A == 0)[0]

        C = np.fft.fft(c)
        C[idx] = 0
        A[idx] = 1
        H = C / A

        H = H[:int(N/2)]
        H_all[k, :] = H

        if plot:
            ax1 = plt.subplot(211)
            ax1.plot(fr, abs(H))
            ax2 = plt.subplot(212)
            ax2.plot(fr, np.unwrap(np.angle(H)))

    if plot:
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.grid(which="both")
        ax2.set_xscale('log')
        ax2.grid(which="both")
        ax1.set_title(plottitle)

    return H_all, fr


class TF(signal.TransferFunction):
    """ Transfer function
    """
    def __init__(self, *args):
        if len(args) not in [2, 4]:
            raise ValueError("2 (num, den) or 4 (A, B, C, D) arguments "
                             "expected, not {}.".format((len(args))))
        if len(args) == 2:
            super().__init__(args[0], args[1])
        else:
            A, B, C, D = args
            n, d = signal.ss2tf(A, B, C, D)
            super().__init__(n, d)

    def __neg__(self):
        return TF(-self.num, self.den)

    def __mul__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(self_s * other_s)

    def __truediv__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(self_s / other_s)

    def __rtruediv__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(other_s / self_s)

    def __add__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(self_s + other_s)

    def __sub__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(self_s - other_s)

    def __rsub__(self, other):
        self_s = self.to_sympy()
        other_s = self._check_other(other)
        return TF.from_sympy(other_s - self_s)

    def _check_other(self, other):
        if type(other) in [int, float, complex]:
            return other
        else:
            return other.to_sympy()
    # symmetric behaviour for commutative operators
    __rmul__ = __mul__
    __radd__ = __add__

    def to_sympy(self, symbol='s', simplify=True):
        """ Convert Scipy's LTI instance to Sympy expression """
        return poly_to_sympy(self.num, self.den, 's', simplify)

    def from_sympy(xpr, symbol='s'):
        """ Convert Sympy transfer function polynomial to Scipy LTI """
        num, den = poly_from_sympy(xpr, symbol)
        return TF(num, den)

    def as_poly_s(self):
        return self.to_sympy()

    def as_poly_z(self, Ts):
        [numz], denz, _ = signal.cont2discrete((self.num, self.den), Ts,
                                               method='bilinear')
        return poly_to_sympy(numz, denz, 'z')

    def apply_f(self, u, x, Ts):
        if self.den.size == 1 and self.num.size == 1:
            return u*self.num[0]/self.den[0], x
        if type(u) is not np.ndarray:
            u = np.array([[u]]).T
        else:
            if u.ndim == 1:
                u = u.reshape((u.size, 1))
            elif u.shape[1] != 1:
                u = u.T

        A_t, B_t, C_t, D_t = signal.tf2ss(self.num, self.den)
        (A, B, C, D, _) = signal.cont2discrete((A_t, B_t, C_t, D_t), Ts,
                                               method='bilinear')

        A = np.kron(np.eye(u.size), A)
        B = np.kron(np.eye(u.size), B)
        C = np.kron(np.eye(u.size), C)
        D = np.kron(np.eye(u.size), D)

        x_vec = x.reshape((x.size, 1))
        x1_vec = A.dot(x_vec) + B.dot(u)
        y = C.dot(x_vec) + D.dot(u)

        # put back in same order
        if type(u) is not np.ndarray:
            y = y[0, 0]
        else:
            if u.ndim == 1:
                y = y.reshape(y.size)
            elif u.shape[1] != 1:
                y = y.T
        if np.any(abs(y.imag) > 0):
            print('y has complex part {}'.format(y))
            print((A, B, C, D))
        return y.reshape(y.size).real, x1_vec.reshape(x.shape)

    def plot_hw(self, w=None, ylabel=None, bode=False, xscale='log', yscale='log',
                figsize=None):
        w, H = signal.freqresp((self.num,self.den), w)

        if bode:
            y = 20*np.log10(abs(H))
            x = w
            yscale = 'linear'
            xlabel = r"Angular frequency $\omega$ [in rad/s]"
        else:
            if yscale == 'db':
                y = 20*np.log10(abs(H))
                yscale = 'linear'
            else:
                y = abs(H)
                yscale = 'log'
            x = w/2/np.pi
            xlabel = r"Frequency f [in Hz]"

        plt.figure(figsize=figsize)
        plt.subplot(2, 1, 1)
        plt.plot(x, y)
        plt.yscale(yscale)
        plt.xlabel(xlabel)
        plt.xscale(xscale)
        #plt.yticks(np.arange(-120,20,30))
        plt.grid(which="both")
        plt.ylabel(ylabel if ylabel is not None else "Amplitude")

        plt.subplot(2, 1, 2)
        plt.plot(x, np.unwrap(np.angle(H))*180/np.pi)
        plt.xscale(xscale)
        plt.grid(which="both")
        plt.yticks(np.arange(-110,30,40))
        plt.xlabel(xlabel)
        plt.ylabel("Phase [in deg]")
        plt.tight_layout(True)

    def plot_step(self, ylabel=None, figsize=None):
        t, y = signal.step((self.num, self.den))

        n_zeros = int(t.size * 0.1)
        T = t[1]

        r = np.concatenate((np.zeros(n_zeros), np.ones(t.size)))
        t = np.concatenate(((np.arange(n_zeros)-n_zeros)*T, t))
        y = np.concatenate((np.zeros(n_zeros), y))

        plt.figure(figsize=figsize)
        plt.plot(t, r)
        plt.plot(t, y)
        plt.xlabel('Time [in s]')
        plt.ylabel(ylabel if ylabel is not None else "Amplitude")
        plt.tight_layout()


class PID(TF):
    def __init__(self, P, I, D):
        tf = TF([P], [1])
        if I != 0:
            tf += TF([I], [1, 0])
        if D != 0:
            tf += TF([D, 0], [D/8, 1])
        super().__init__(tf.num, tf.den)

        self.kP = P
        self.kI = I
        self.kD = D

    def apply_fd(self, e, Ts):
        return (self.kP*e[:, -1] + self.kI*np.sum(e, axis=1)*Ts
                                 + self.kD*(e[:, -1]-e[:, -2])/Ts)

    def apply_f(self, e, x, Ts):
        return TF.apply_f(self, e, x, Ts)
