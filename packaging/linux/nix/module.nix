{ config, lib, pkgs, ... }:

let
  cfg = config.services.sidee;
in
{
  options.services.sidee = {
    enable = lib.mkEnableOption ''
      the Sidee dashboard, which manages web-app launcher tiles on a VIDAA TV
      on the local network
    '';

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./package.nix { };
      defaultText = lib.literalExpression "pkgs.callPackage ./package.nix { }";
      description = "The Sidee package to use.";
    };

    port = lib.mkOption {
      type = lib.types.nullOr lib.types.port;
      default = null;
      example = 8787;
      description = ''
        Port for the local dashboard. The default (null) asks Sidee to open on
        port 8787 and fall back to a free port when it is already in use.
      '';
    };

    installToSystem = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Add Sidee to {option}`environment.systemPackages` so the `sidee`
        command and the desktop entry are available to every user.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = lib.mkIf cfg.installToSystem [ cfg.package ];

    systemd.user.services.sidee = {
      description = "Sidee local dashboard for VIDAA TV launcher tiles";
      documentation = [ "https://github.com/Empi9245/Sidee" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "default.target" ];
      restartIfChanged = true;
      serviceConfig = {
        ExecStart = "${lib.getExe cfg.package} --headless"
          + lib.optionalString (cfg.port != null) " --port ${toString cfg.port}";
        Restart = "on-failure";
        RestartSec = 5;
        # The dashboard URL contains the private access key.
        StandardOutput = "null";
      };
    };
  };
}
