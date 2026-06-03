/* Shared property-inspector glue: registers with Stream Deck, loads settings
 * into the form, saves on change. Pages define loadForm(settings) and
 * readForm() -> settings. */

"use strict";

let piWs = null, piUuid = null, piSettings = {};

function connectElgatoStreamDeckSocket(inPort, inUUID, inRegisterEvent, _inInfo, inActionInfo) {
  piUuid = inUUID;
  const info = JSON.parse(inActionInfo);
  piSettings = (info.payload && info.payload.settings) || {};
  piWs = new WebSocket("ws://127.0.0.1:" + inPort);
  piWs.onopen = () => {
    piWs.send(JSON.stringify({ event: inRegisterEvent, uuid: inUUID }));
    loadForm(piSettings);
  };
}

function save(partial) {
  Object.assign(piSettings, partial);
  piWs.send(JSON.stringify({ event: "setSettings", context: piUuid, payload: piSettings }));
}

function saveForm() {
  save(readForm());
}
