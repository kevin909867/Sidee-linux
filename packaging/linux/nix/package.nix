{ lib
, stdenvNoCC
, python3
, makeWrapper
, version ? "0.1.4.2"
}:

let
  # Sidee needs exactly one Python dependency. Building it into the wrapped
  # interpreter keeps the package hermetic and free of runtime PYTHONPATH hacks.
  python = python3.withPackages (ps: [ ps.paho-mqtt ]);
  desktopEntry = ../sidee.desktop;
  # Keep local pairings, runtimes and build output out of the Nix store.
  excluded = [ ".git" ".runtime" ".sidee" ".venv" ".vidaa-tile" "dist" "build"
               "__pycache__" "session.json" "certs.bin.k" "dashboard.json" ];
in
stdenvNoCC.mkDerivation {
  pname = "sidee";
  inherit version;

  src = lib.cleanSourceWith {
    src = ../../..;
    filter = path: _type: !(builtins.elem (baseNameOf (toString path)) excluded);
  };

  nativeBuildInputs = [ makeWrapper ];
  buildInputs = [ python ];

  dontBuild = true;
  dontConfigure = true;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/sidee
    cp -R sidee.py core assets docs README.md LICENSE $out/share/sidee/

    makeWrapper ${python}/bin/python3 $out/bin/sidee \
      --add-flags "$out/share/sidee/sidee.py"

    mkdir -p $out/share/applications $out/share/pixmaps
    # TryExec first: its text contains "Exec=sidee", so replacing Exec first
    # would rewrite both keys and leave this second pattern unmatched.
    substitute ${desktopEntry} $out/share/applications/sidee.desktop \
      --replace-fail "TryExec=sidee" "TryExec=$out/bin/sidee" \
      --replace-fail "Exec=sidee" "Exec=$out/bin/sidee"
    install -Dm644 assets/sidee-logo.png $out/share/pixmaps/sidee.png

    runHook postInstall
  '';

  meta = {
    description = "Manage web-app launcher tiles on your VIDAA TV";
    homepage = "https://github.com/Empi9245/Sidee";
    license = lib.licenses.mit;
    mainProgram = "sidee";
    platforms = lib.platforms.linux;
  };
}
