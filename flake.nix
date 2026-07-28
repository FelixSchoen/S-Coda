{
  description = "Python development environment with optional GPU support";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";
  };

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgsBase = import nixpkgs {
        inherit system;
      };
      pkgsGpu = import nixpkgs {
        inherit system;
        config = {
          allowUnfree = true;
          cudaSupport = true;
        };
      };

      # On NixOS, the NVIDIA driver is managed by the system configuration.
      # We use /run/opengl-driver which is symlinked by NixOS to the correct driver.
      # This avoids driver version mismatches between the flake and system.
      nixosDriverPath = "/run/opengl-driver";

      # CUDA toolkit
      cudaToolkit = pkgsGpu.cudaPackages.cudatoolkit;

      # Base library dependencies (always included)
      baseLibs =
        pkgs: with pkgs; [
          stdenv.cc.cc.lib
          zlib
          zstd
          openssl
          curl
          bzip2
          xz
          libxml2
          util-linux
          systemd
          ncurses
          attr
          libssh
          acl
          libsodium
        ];

      # GPU libraries (CUDA + cuDNN + Graphics/X11)
      gpuLibs = with pkgsGpu; [
        # Graphics/X11
        libGL
        libGLU
        libx11
        libxext
        libxrender
        libxrandr
        libxi
        libxcursor
        libxfixes
        libxmu
        libxv
        libxkbcommon
        freeglut
      ];

      # Configurable Python shell builder
      makePythonShell =
        pkgs:
        {
          python ? pkgs.python313,
          withGpu ? false,
          withPythonTools ? true,
        }:
        let
          # Current nixpkgs no longer keeps every tool in the Python 3.11
          # package set evaluable. Python itself still provides venv and
          # ensurepip, so that shell can use the interpreter directly.
          pythonEnv =
            if withPythonTools then
              python.withPackages (
                ps: with ps; [
                  pip
                  virtualenv
                ]
              )
            else
              python;

          basePackages = baseLibs pkgs;

          # Build package list based on options
          # Note: We do NOT include a driver package - we use the system driver
          gpuPackages =
            if withGpu then
              [
                cudaToolkit
                pkgsGpu.cudaPackages.cudnn
              ]
              ++ gpuLibs
            else
              [ ];

          # Build library path - include NixOS driver path for GPU
          libPath = pkgs.lib.makeLibraryPath (basePackages ++ (if withGpu then gpuLibs else [ ]));

          # Shell hook for GPU/CUDA configuration
          gpuShellHook =
            if withGpu then
              ''
                # CUDA configuration
                export CUDA_PATH="${cudaToolkit}"
                export CUDA_HOME="${cudaToolkit}"
                export CUDA_DEVICE_ORDER="PCI_BUS_ID"
                export CUDA_LAUNCH_BLOCKING=0

                # Use NixOS system driver via /run/opengl-driver
                # This is the correct way to access GPU drivers on NixOS
                export LD_LIBRARY_PATH="${nixosDriverPath}/lib:${cudaToolkit}/lib:${cudaToolkit}/lib64:${pkgsGpu.cudaPackages.cudnn}/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

                # Triton-specific configuration for NixOS
                # Point to system driver for libcuda.so
                export TRITON_LIBCUDA_PATH="${nixosDriverPath}/lib"
                export TRITON_PTXAS_PATH="${cudaToolkit}/bin/ptxas"
                export TRITON_CUOBJDUMP_PATH="${cudaToolkit}/bin/cuobjdump"
                export TRITON_NVDISASM_PATH="${cudaToolkit}/bin/nvdisasm"

                # Triton cache and runtime settings
                export TRITON_CACHE_DIR="/var/tmp/triton-cache-$UID"
                mkdir -p "$TRITON_CACHE_DIR"
                export TRITON_IGNORE_UNKNOWN_PARAMETERS=1
                export TRITON_PRINT_AUTOTUNING=0  # Set to 1 for debugging
              ''
            else
              "";

          gpuStatus = if withGpu then "✓ GPU stack enabled (CUDA + cuDNN + Graphics)" else "✗ GPU disabled";

        in
        pkgs.mkShell {
          name = "python-dev";

          packages = [
            pythonEnv

            # Build tools
            pkgs.gcc
            pkgs.gnumake
            pkgs.cmake
            pkgs.pkg-config
            pkgs.binutils

            # Version control
            pkgs.git

            # Media helpers used by music/data workflows
            pkgs.ffmpeg
            pkgs.fluidsynth
          ]
          ++ basePackages
          ++ gpuPackages;

          shellHook = ''
            # Library paths
            export LD_LIBRARY_PATH="${libPath}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
            nix_python_version="$("${pythonEnv}/bin/python" --version 2>&1)"

            # Compiler configuration
            export CC="${pkgs.gcc}/bin/gcc"
            export CXX="${pkgs.gcc}/bin/g++"

            ${gpuShellHook}

            # Auto-activate venv if it exists
            venv_path="$PWD/.venv"
            if [ -d "$venv_path" ]; then
              # The shared zsh prompt already renders the active venv name.
              # Keep Python's activate script from prepending its own prompt
              # fragment and avoid re-sourcing when direnv reloads the same venv.
              export VIRTUAL_ENV_DISABLE_PROMPT=1
              if [ "''${VIRTUAL_ENV:-}" != "$venv_path" ]; then
                source "$venv_path/bin/activate"
              fi

              # If nix develop inherits VIRTUAL_ENV from direnv, activation is
              # skipped above; keep the local venv ahead of Nix's Python tools.
              case "$PATH" in
                "$venv_path/bin":*) ;;
                *) export PATH="$venv_path/bin:$PATH" ;;
              esac
            fi

            # Environment info
            active_python_version="$(python --version 2>&1)"
            echo ""
            echo "🐍 $active_python_version development environment"
            if [ "$active_python_version" != "$nix_python_version" ]; then
              echo "   Nix shell provides: $nix_python_version"
            fi
            echo ""
            echo "📦 Virtual environment:"
            if [ -d ".venv" ]; then
              echo "   ✓ .venv activated"
              if [ "$active_python_version" != "$nix_python_version" ]; then
                echo "   ! Recreate .venv to move it onto the current Nix Python"
              fi
            else
              echo "   ✗ No .venv found. Run: python -m venv .venv && source .venv/bin/activate"
            fi
            echo ""
            echo "🔧 Features:"
            echo "   ${gpuStatus}"
            echo ""
          '';
        };

    in
    {
      devShells.${system} = {
        # Default: basic Python, no GPU
        default = makePythonShell pkgsBase { };

        # GPU: full stack (CUDA + cuDNN + Graphics)
        gpu = makePythonShell pkgsGpu { withGpu = true; };

        # Python version variants - default (no GPU)
        py311 = makePythonShell pkgsBase {
          python = pkgsBase.python311;
          withPythonTools = false;
        };
        py312 = makePythonShell pkgsBase { python = pkgsBase.python312; };
        py313 = makePythonShell pkgsBase { python = pkgsBase.python313; };
        py314 = makePythonShell pkgsBase { python = pkgsBase.python314; };

        # Python version variants - GPU
        gpu-py311 = makePythonShell pkgsGpu {
          python = pkgsGpu.python311;
          withGpu = true;
          withPythonTools = false;
        };
        gpu-py312 = makePythonShell pkgsGpu {
          python = pkgsGpu.python312;
          withGpu = true;
        };
        gpu-py313 = makePythonShell pkgsGpu {
          python = pkgsGpu.python313;
          withGpu = true;
        };
        gpu-py314 = makePythonShell pkgsGpu {
          python = pkgsGpu.python314;
          withGpu = true;
        };
      };
    };
}
