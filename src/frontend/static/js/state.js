// state.js — Shared mutable state hub
// Every other module imports from here; this module imports nothing.

const state = {
    robotPose: { x: 0, y: 0, theta: 0 },
    mapInfo: null,
    isMapLoaded: false,
    mapImage: new Image(),
    canvasScale: 1,

    isDragging: false,
    dragStart: null,
    dragCurrent: null,

    currentPatrolPoints: [],
    highlightedPoint: null,

    currentSettingsTimezone: 'UTC',
    currentIdleStreamEnabled: true,
};

export default state;
