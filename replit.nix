{ pkgs }: {
    deps = [
        pkgs.python39
        pkgs.python39Packages.pip
        pkgs.python39Packages.fastapi
        pkgs.python39Packages.uvicorn
        pkgs.python39Packages.websockets
        pkgs.python39Packages.pillow
    ];
} 