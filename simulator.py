# Simulated hardware layer for the Zaber stage console.
# Stands in for real stages: each axis moves toward its target over time, so the
# position readouts animate and the status pills switch between MOVING and IDLE.

import time


class SimAxis:
    # One simulated axis, linear (mm) or rotary (deg).
    def __init__(self, label, travel_min, travel_max, max_velocity, is_rotary=False):
        self.label = label
        self.is_rotary = is_rotary
        self.unit_label = "deg" if is_rotary else "mm"
        self.vel_label = "deg/s" if is_rotary else "mm/s"
        self.max_velocity = max_velocity
        self.travel_min = travel_min
        self.travel_max = travel_max

        self._pos = travel_min
        self._target = travel_min
        self._vel = 0.0            # effective speed of the current move, unit/s
        self._last = time.monotonic()

    def _check(self, target):
        # Clamp to range, raising on real overtravel (small slack for rounding).
        if not (self.travel_min - 1e-3 <= target <= self.travel_max + 1e-3):
            raise ValueError(
                f"{target:.3f} {self.unit_label} is outside this stage's range "
                f"({self.travel_min:.1f} to {self.travel_max:.1f} {self.unit_label})."
            )
        return min(max(target, self.travel_min), self.travel_max)

    def _speed(self, velocity):
        # 0 (blank field) means device default: 40% of max.
        if velocity and velocity > 0:
            return min(velocity, self.max_velocity)
        return self.max_velocity * 0.4

    def _advance(self):
        # Move the position toward the target by the time elapsed since last read.
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        if self._pos == self._target:
            return
        step = self._vel * dt
        delta = self._target - self._pos
        if abs(delta) <= step:
            self._pos = self._target
        else:
            self._pos += step * (1 if delta > 0 else -1)

    # --- interface the GUI calls ---
    def home(self):
        self._vel = self._speed(0)
        self._target = self.travel_min

    def jog(self, distance, velocity=0):
        self.move_absolute(self._pos + distance, velocity)

    def move_absolute(self, position, velocity=0):
        self._target = self._check(position)
        self._vel = self._speed(velocity)

    def stop(self):
        self._advance()
        self._target = self._pos

    def position(self):
        self._advance()
        return self._pos

    def is_busy(self):
        return abs(self._pos - self._target) > 1e-6


class StageController:
    # Simulated multi-axis controller. connect() always succeeds and hands back
    # a fixed set of axes.
    def __init__(self, port="SIM1"):
        self.port = port
        self._connected = False
        self.axes = []

    @property
    def is_connected(self):
        return self._connected

    def connect(self):
        self.axes = [
            SimAxis("Linear stage 1", 0.0, 150.0, 300.0),
            SimAxis("Linear stage 2", 0.0, 100.0, 250.0),
            SimAxis("Rotary stage", 0.0, 360.0, 200.0, is_rotary=True),
        ]
        self._connected = True
        return self.axes

    def stop_all(self):
        errors = []
        for handle in self.axes:
            try:
                handle.stop()
            except Exception as exc:
                errors.append((handle.label, exc))
        return errors

    def disconnect(self):
        self.axes = []
        self._connected = False
