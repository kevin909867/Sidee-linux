{
  description = "Sidee: add web apps as permanent tiles to your VIDAA TV launcher";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = function:
        nixpkgs.lib.genAttrs systems
          (system: function nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (pkgs: rec {
        sidee = pkgs.callPackage ./packaging/linux/nix/package.nix { };
        default = sidee;
      });

      apps = nixpkgs.lib.genAttrs systems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.sidee}/bin/sidee";
          meta.description = "Open the Sidee dashboard";
        };
      });

      overlays.default = _final: prev: {
        sidee = prev.callPackage ./packaging/linux/nix/package.nix { };
      };

      nixosModules = rec {
        sidee = import ./packaging/linux/nix/module.nix;
        default = sidee;
      };
    };
}
