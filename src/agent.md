# Qt/C++ Development Agent Guide

## 1. Mission
You are a Senior Qt/C++ Developer. Your goal is to rehost the JEOL 5600 control software to Linux using modern Qt 6 (or Qt 5 if necessary).

## 2. Project Structure
*   **Root**: `content/src/sem/` (Qt Project Root)
*   **Build System**: CMake
*   **Framework**: Qt 6 (Widgets Module)
*   **Standard**: C++17

## 3. Build & Test Commands
Run these commands from `content/src/` (the parent of `sem`):

### Build
```bash
# Configure
cmake -S sem -B build

# Build
cmake --build build

# Clean Rebuild
rm -rf build && cmake -S sem -B build && cmake --build build
```

### Run
```bash
./build/sem
```

### Test
*Currently, no unit tests are implemented.*
In the future, use:
```bash
cd build && ctest --output-on-failure
# Run single test:
# ctest -R <TestName> --verbose
```

## 4. Code Style & Conventions
*   **Naming**:
    *   Classes: `PascalCase` (e.g., `MainWindow`, `SemController`)
    *   Methods/Variables: `camelCase` (e.g., `startEvacuation()`, `currentVoltage`)
    *   Member Variables: Prefix with `m_` (e.g., `m_isConnected`)
    *   Constants: `kPascalCase` or `SCREAMING_SNAKE_CASE`
*   **Files**:
    *   Headers in `.h`, Implementation in `.cpp`.
    *   One class per file ideally.
*   **Qt Best Practices**:
    *   Use `connect` with function pointers (new syntax), NOT `SIGNAL`/`SLOT` macros.
    *   Use `std::unique_ptr` or `QScopedPointer` for non-QObject resources.
    *   Use Qt Parent-Child ownership for `QObject` memory management.
    *   **Tr()**: Always wrap user-facing strings in `tr("String")` for internalization (zh_TW).

## 5. Implementation Roadmap
Refer to `../../docs/srs/srs.md` for logic and `../../docs/srs/user_srs.md` for UI specifications.

### Phase 1: Hardware Abstraction Layer (HAL)
*   Create a `ScsiCommunicator` class.
*   Implement the commands defined in `../../docs/pins_protocol.md`.
*   **Simulation**: Since hardware might be missing, create a `MockScsiBackend` that returns fake status (e.g., Vacuum=Ready) for UI testing. Use an interface `ISemBackend` to switch between `ScsiBackend` and `MockBackend`.

### Phase 2: UI Implementation (Dark Mode)
*   Implement `MainWindow` based on `user_srs.md` (Dark Theme #2D2D2D).
*   Create Custom Widgets: `KnobWidget`, `SemMonitorWidget` (Vacuum/HT status).
*   Implement `QPainter` based custom drawing for the "Radar" or "Vacuum Gauge".

### Phase 3: Logic Integration
*   Connect UI signals to HAL slots.
*   Implement the "Safety Interlock" (e.g., disable HT button if Vacuum != Ready).

## 6. Error Handling
*   Do NOT use exceptions for flow control. Use `std::optional` or return codes.
*   For UI errors, show a non-blocking `QFrame` or `QStatusBar` message (Toast), avoid `QMessageBox` for runtime errors during operation.
