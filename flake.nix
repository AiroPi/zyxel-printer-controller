{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

  };
  outputs =
    inputs@{ flake-parts, nixpkgs, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = builtins.attrNames nixpkgs.legacyPackages;
      perSystem =
        { pkgs, lib, ... }:
        let
          pythonDeps =
            ps: with ps; [
              httpx2
              fastapi
              uvicorn
            ];
        in
        {
          devShells.default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages pythonDeps)
            ];
          };
          packages.default =
            let
              pkgs = import nixpkgs { system = "aarch64-linux"; };
              app = lib.fileset.toSource {
                root = ./.;
                fileset = ./server.py;
              };
            in
            pkgs.dockerTools.buildLayeredImage {
              name = "zyxel-printer-server";
              tag = "latest";
              contents = [
                (pkgs.python3.withPackages pythonDeps)
                pkgs.bash
                pkgs.coreutils
                app
              ];
              config = {
                Cmd = [
                  "python3"
                  "server.py"
                ];
              };
            };
        };
    };
}
