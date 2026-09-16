import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

const $ = id => document.getElementById(id);

if (new URLSearchParams(location.search).has('embed')) {
    document.body.classList.add('embed');
}

// ============================================================
// SCENE
// ============================================================

const scene = new THREE.Scene();
scene.background = new THREE.Color('#091820');

// ============================================================
// CAMERA
// ============================================================

const camera = new THREE.PerspectiveCamera(
    45,
    1,
    0.1,
    10000
);

// ============================================================
// RENDERER
// ============================================================

let renderer;

try {

    renderer = new THREE.WebGLRenderer({
        antialias: true
    });

}
catch (e) {

    $('status').textContent =
        '3D rendering is unavailable. Enable WebGL or try another browser.';

    throw e;
}

renderer.setPixelRatio(
    Math.min(devicePixelRatio, 2)
);

renderer.setSize(
    800,
    600
);

renderer.outputColorSpace =
    THREE.SRGBColorSpace;

$('viewport').append(
    renderer.domElement
);

// ============================================================
// CONTROLS
// ============================================================

const controls =
    new OrbitControls(
        camera,
        renderer.domElement
    );

// Stop orbiting as soon as the pointer is released.
controls.enableDamping = false;

// ============================================================
// LIGHTING
// ============================================================

scene.add(
    new THREE.HemisphereLight(
        0xddecff,
        0x66767f,
        2.2
    )
);

const sun =
    new THREE.DirectionalLight(
        0xffffff,
        2.5
    );

sun.position.set(
    100,
    400,
    200
);

scene.add(sun);

// ============================================================
// LOADER / RAYCASTER
// ============================================================

const loader =
    new GLTFLoader();

const raycaster =
    new THREE.Raycaster();

// ============================================================
// GLOBAL STATE
// ============================================================

let root = null;
let records = [];
let meshes = [];

let highlight = null;

let sensorMarkerGroup = null;
let sensorMarkerMeshes = [];
let sensorMarkerButtons = [];
let sensorMarkerRevealDistance = 50;

const sensorDefinitions = [
    { id: 'ACC_01',
        label: 'Acceleration',
        location: 'Middle of BR1 Tie Girder -1',
        colour: 0xff5b5b,

        // Exact object family:
        // _BR1_Tie_Girder_-1_1246474
        pattern: /_BR1_Tie_Girder_-1_/i,

        // Middle of the selected tie girder
        along: 0.5,

        // Place marker on bottom surface
        face: 'bottom',

        // First object matching this specific pattern
        targetIndex: 0,

        // Only moves the label on the screen
        screenOffset: [-0, 20]},
    {    id: 'TEMP_01',
    label: 'Temperature',
    location: 'Middle top of BR1 Upper Cross Brace 4',
    colour: 0x68d391,

    // Exact target object:
    // _BR1_Upper_Cross_Brace_4_1246537
    pattern: /_BR1_Upper_Cross_Brace_4_/i,

    // Middle of the brace
    along: 0.5,

    // Top surface
    face: 'top',

    // First object matching this specific pattern
    targetIndex: 0,

    // Keep label close to the marker
    screenOffset: [0, -20]},
    {     id: 'SG_01',
    label: 'Strain',
    location: 'Middle bottom of BR1 Tie Girder 1',
    colour: 0xffc857,

    // Exact target object:
    // _BR1_Tie_Girder_1_1246498
    pattern: /_BR1_Tie_Girder_1_/i,

    // Middle of the girder
    along: 0.5,

    // Bottom surface
    face: 'bottom',

    // First object matching this specific pattern
    targetIndex: 0,

    // Keep label close to the marker
    screenOffset: [0, 20]},
    {     id: 'DISP_01',
    label: 'Displacement',
    location: 'Top-right corner of BR1 T6 Support',
    colour: 0x70b7ff,

    // Exact target object:
    // _BR1_T6_Support_1246546
    pattern: /_BR1_T6_Support_/i,

    // Move toward the right end of the support
    along: 0.85,

    // Place marker on the top face
    face: 'top',

    // First object matching this specific pattern
    targetIndex: 0,

    // Keep label close to marker
    screenOffset: [18, -18] }
];

let loadNumber = 0;

let measuring = false;
let points = [];
let line = null;

// ============================================================
// IMPORTANT
// DO NOT MOVE THE BRIDGE ON THE WEBSITE
// Geometry position now comes directly from Revit / Blender.
// ============================================================

const BRIDGE_RAISE = 0.0;

// ============================================================
// IDENTIFY BRIDGE OBJECTS
// Used only for Fit Bridge and Show Surrounding Site.
// It does NOT change geometry or colour.
// ============================================================

const isBridge = o =>
    /\bBR[12]\b|arch|hanger|pier|deck|bearing|tie.?girder|support|column|abutment|beam|girder|brace/i
        .test(o.name);

// ============================================================
// PREPARE ORIGINAL GLB MATERIAL
// KEEP COLOURS FROM BLENDER / REVIT
// ============================================================

function prepareOriginalMaterial(object) {

    if (!object.material) {
        return;
    }

    const materials =
        Array.isArray(object.material)
            ? object.material
            : [object.material];

    materials.forEach(material => {

        if (!material) {
            return;
        }

        // Make surfaces visible from both sides.
        material.side =
            THREE.DoubleSide;

        // Preserve original GLB colour,
        // opacity, textures, roughness, etc.
        material.needsUpdate =
            true;
    });
}

// ============================================================
// DISPOSE OLD MODEL
// ============================================================

function disposeModel(model) {

    if (!model) {
        return;
    }

    const geometries =
        new Set();

    const materials =
        new Set();

    const textures =
        new Set();

    model.traverse(o => {

        if (o.geometry) {
            geometries.add(o.geometry);
        }

        const mats =
            Array.isArray(o.material)
                ? o.material
                : o.material
                    ? [o.material]
                    : [];

        mats.forEach(material => {

            if (!material) {
                return;
            }

            materials.add(material);

            Object.values(material).forEach(value => {

                if (value?.isTexture) {
                    textures.add(value);
                }
            });
        });
    });

    textures.forEach(
        texture => texture.dispose()
    );

    materials.forEach(
        material => material.dispose()
    );

    geometries.forEach(
        geometry => geometry.dispose()
    );
}

// ============================================================
// REMOVE HIGHLIGHT
// ============================================================

function clearHighlight() {

    if (!highlight) {
        return;
    }

    scene.remove(highlight);

    if (highlight.dispose) {
        highlight.dispose();
    }
    else {

        highlight.geometry?.dispose();
        highlight.material?.dispose();
    }

    highlight = null;
}

function clearSensorMarkers() {

    if (!sensorMarkerGroup) {
        return;
    }

    sensorMarkerGroup.traverse(o => {
        o.geometry?.dispose();
        o.material?.dispose();
        o.material?.map?.dispose();
    });

    scene.remove(sensorMarkerGroup);
    sensorMarkerButtons.forEach(button => button.remove());
    sensorMarkerGroup = null;
    sensorMarkerMeshes = [];
    sensorMarkerButtons = [];
}

function notifySensorSelection(sensor) {

    selectSensorMarker(sensor);

    if (window.parent !== window) {
        window.parent.postMessage(
            { type: 'bridge-sensor-selected', id: sensor.id },
            window.location.origin
        );
    }
}

function positionSensorMarkerButtons() {

    const rect = renderer.domElement.getBoundingClientRect();
    const closeEnough =
        camera.position.distanceTo(controls.target)
        <= sensorMarkerRevealDistance;

    if (sensorMarkerGroup) {
        sensorMarkerGroup.visible = closeEnough;
    }

    sensorMarkerButtons.forEach(({ button, pin }) => {
        const point = pin.getWorldPosition(new THREE.Vector3()).project(camera);
        const visible = closeEnough && point.z >= -1 && point.z <= 1 && Math.abs(point.x) <= 1.08 && Math.abs(point.y) <= 1.08;
        button.hidden = !visible;
        if (visible) {
            button.style.left = ((point.x + 1) * 0.5 * rect.width) + 'px';
            button.style.top = ((1 - point.y) * 0.5 * rect.height) + 'px';
        }
    });
}

function sensorLabel(text, colour, radius) {

    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 76;
    const context = canvas.getContext('2d');

    context.fillStyle = '#081820';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = '#' + colour.toString(16).padStart(6, '0');
    context.lineWidth = 5;
    context.strokeRect(3, 3, canvas.width - 6, canvas.height - 6);
    context.fillStyle = '#f1fbff';
    context.font = 'bold 30px system-ui';
    context.fillText(text, 18, 48);

    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map: new THREE.CanvasTexture(canvas),
        depthTest: false,
        transparent: true
    }));
    sprite.scale.set(radius * 12, radius * 3, 1);
    return sprite;
}

function addSensorMarkers() {

    clearSensorMarkers();

    const bridgeMeshes = meshes.filter(isBridge);
    const bridgeBox = new THREE.Box3();
    bridgeMeshes.forEach(o => bridgeBox.expandByObject(o));

    if (bridgeBox.isEmpty()) {
        return;
    }

    const bridgeSize = bridgeBox.getSize(new THREE.Vector3());
    const markerRadius = Math.max(0.45, Math.min(1.4, Math.max(bridgeSize.x, bridgeSize.y) / 140));
    const mainSpanBox = bridgeMeshes
        .filter(o => /arch rib/i.test(o.name))
        .reduce((box, o) => box.expandByObject(o), new THREE.Box3());
    const mainSpanLength = mainSpanBox.isEmpty()
        ? bridgeSize.x
        : mainSpanBox.getSize(new THREE.Vector3()).x;
    sensorMarkerRevealDistance = Math.max(50, mainSpanLength *0.5);
    sensorMarkerGroup = new THREE.Group();
    sensorMarkerGroup.name = 'Sensor markers';
    scene.add(sensorMarkerGroup);

    sensorDefinitions.forEach((sensor, index) => {
        let candidates = bridgeMeshes.filter(o => sensor.pattern.test(o.name));
        if (!candidates.length && sensor.fallback) {
            candidates = bridgeMeshes.filter(o => sensor.fallback.test(o.name));
        }
        const target = candidates[(sensor.targetIndex || 0) % Math.max(candidates.length, 1)];
        const box = target ? new THREE.Box3().setFromObject(target) : bridgeBox;
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const position = new THREE.Vector3(
            box.min.x + size.x * sensor.along,
            sensor.face === 'bottom'
                ? box.min.y - markerRadius * 1.8
                : box.max.y + markerRadius * 1.8,
            center.z
        );

        const pin = new THREE.Mesh(
            new THREE.SphereGeometry(markerRadius, 20, 14),
            new THREE.MeshBasicMaterial({ color: sensor.colour, depthTest: false })
        );
        pin.position.copy(position);
        pin.renderOrder = 10;
        pin.userData.sensor = { ...sensor, element: target?.name || 'Bridge reference location' };
        sensorMarkerGroup.add(pin);
        sensorMarkerMeshes.push(pin);

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'sensor-marker';
        // Customize size here
        button.style.fontSize = '9px';
        button.style.padding = '2px 5px';
        button.style.minWidth = '38px';
        button.style.height = '22px';
        button.style.borderRadius = '11px';
        


        button.textContent = sensor.id;
        button.title = sensor.label + ' · ' + sensor.location;
        button.setAttribute('aria-label', sensor.label + ' sensor ' + sensor.id + ' at ' + sensor.location);
        button.style.color = '#' + sensor.colour.toString(16).padStart(6, '0');
        button.style.setProperty('--pin-offset-x', (sensor.screenOffset?.[0] || 0) + 'px');
        button.style.setProperty('--pin-offset-y', (sensor.screenOffset?.[1] || 0) + 'px');
        button.addEventListener('click', () => notifySensorSelection(pin.userData.sensor));
        $('viewport').append(button);
        sensorMarkerButtons.push({ button, pin });

    });

    console.log('Mapped sensor markers:', sensorMarkerMeshes.length);
}

function selectSensorMarker(sensor) {

    clearHighlight();
    $('selection').textContent =
        'Sensor: ' + sensor.id + '\n' +
        'Type: ' + sensor.label + '\n' +
        'Mapped location: ' + sensor.location + '\n' +
        'Model element: ' + sensor.element + '\n' +
        'Status: live reading available on the sensor dashboard.';
    $('status').textContent = sensor.id + ' · ' + sensor.label + ' · ' + sensor.location;
}

// ============================================================
// FIT CAMERA
// ============================================================

function fit(
    bridgeOnly = false
) {

    if (!root) {
        return;
    }

    const box =
        new THREE.Box3();

    if (bridgeOnly) {

        meshes
            .filter(isBridge)
            .filter(o => o.visible)
            .forEach(
                o => box.expandByObject(o)
            );
    }

    if (box.isEmpty()) {

        box.setFromObject(root);
    }

    const center =
        box.getCenter(
            new THREE.Vector3()
        );

    const size =
        box.getSize(
            new THREE.Vector3()
        );

    const largestDimension =
        Math.max(
            size.x,
            size.y,
            size.z
        );

    const distance =
        largestDimension
        /
        (
            2 *
            Math.tan(
                THREE.MathUtils.degToRad(
                    camera.fov / 2
                )
            )
        )
        *
        1.3
        /
        Math.min(
            camera.aspect,
            1
        );

    controls.target.copy(
        center
    );

    camera.position
        .copy(center)
        .add(
            new THREE.Vector3(
                0.7,
                0.65,
                1
            )
            .normalize()
            .multiplyScalar(
                distance
            )
        );

    camera.near =
        Math.max(
            0.01,
            distance / 10000
        );

    camera.far =
        distance * 30;

    camera.updateProjectionMatrix();

    controls.update();
}

// ============================================================
// CLEAR MEASUREMENT
// ============================================================

function clearMeasurement() {

    points = [];

    if (line) {

        scene.remove(line);

        line.geometry.dispose();

        line.material.dispose();

        line = null;
    }
}

// ============================================================
// LOAD GLB MODEL
// ============================================================

async function load(record) {

    const number =
        ++loadNumber;

    $('status').textContent =
        'Loading ' +
        record.name +
        '…';

    $('metadata').textContent =
        record.notes ||
        'Preliminary imported geometry.';

    clearMeasurement();

    clearHighlight();

    $('measure-result').textContent =
        '';

    try {

        const gltf =
            await loader.loadAsync(
                `${record.url}?v=${encodeURIComponent(record.sha256 || record.id)}`
            );

        // Another model started loading before this one finished.
        if (
            number !==
            loadNumber
        ) {

            disposeModel(
                gltf.scene
            );

            return;
        }

        // Remove old model.
        if (root) {

            scene.remove(root);

            disposeModel(root);
        }

        root =
            gltf.scene;

        scene.add(root);

        meshes = [];

        // ====================================================
        // IMPORTANT:
        // Keep original GLB materials and colours.
        // DO NOT replace materials here.
        // DO NOT move individual bridge objects.
        // ====================================================

        root.traverse(o => {

            if (!o.isMesh) {
                return;
            }

            meshes.push(o);

            prepareOriginalMaterial(o);

            // No bridge elevation correction here.
            //
            // With BRIDGE_RAISE = 0 this changes nothing,
            // but it is intentionally kept visible in the code.
            if (
                BRIDGE_RAISE !== 0 &&
                isBridge(o)
            ) {

                o.position.z +=
                    BRIDGE_RAISE;
            }
        });

        addSensorMarkers();

        // ====================================================
        // DIAGNOSTIC
        // ====================================================

        const pierMeshes =
            meshes.filter(
                o =>
                    /pier|support|column|abutment|bearing/i
                        .test(o.name)
            );

        console.log(
            'Loaded model:',
            record.name
        );

        console.log(
            'Total mesh objects:',
            meshes.length
        );

        console.log(
            'Pier/support objects:',
            pierMeshes.length
        );

        console.log(
            'Bridge raise:',
            BRIDGE_RAISE
        );

        // ====================================================
        // RESET INTERFACE
        // ====================================================

        $('context').checked =
            true;

        $('selection').textContent =
            'Click a model object to inspect its export identifier and elevation.';

        fit();

        $('status').textContent =
            record.name +
            ' · ' +
            meshes.length +
            ' mesh objects · Preliminary';

        window.modelViewerState = {

            id:
                record.id,

            meshes:
                meshes.length,

            piers:
                pierMeshes.length,

            bridgeRaise:
                BRIDGE_RAISE,

            sensorMarkers:
                sensorMarkerMeshes.length,

            loaded:
                true
        };
    }

    catch (e) {

        console.error(e);

        if (
            number ===
            loadNumber
        ) {

            $('status').textContent =
                'Could not load model: ' +
                e.message;
        }
    }
}

// ============================================================
// GET MODEL VERSIONS
// ============================================================

async function refresh(
    selected
) {

    const response =
        await fetch(
            '/models',
            {cache: 'no-store'}
        );

    if (!response.ok) {

        throw Error(
            'Model registry unavailable'
        );
    }

    records =
        await response.json();

    $('versions')
        .replaceChildren(
            ...records.map(r => {

                const option =
                    document.createElement(
                        'option'
                    );

                option.value =
                    r.id;

                option.textContent =
                    r.name;

                return option;
            })
        );

    const record =
        records.find(
            r =>
                r.id === selected
        )
        ||
        records[0];

    if (record) {

        $('versions').value =
            record.id;

        await load(record);
    }

    else {

        $('status').textContent =
            'No model uploaded yet.';
    }
}

// ============================================================
// MODEL VERSION CHANGE
// ============================================================

$('versions').onchange =
    () => {

        const record =
            records.find(
                r =>
                    r.id ===
                    $('versions').value
            );

        if (record) {

            load(record);
        }
    };

// ============================================================
// FIT BUTTONS
// ============================================================

$('fit').onclick =
    () => fit(false);

$('bridge').onclick =
    () => fit(true);

// ============================================================
// SHOW / HIDE SURROUNDING SITE
// ============================================================

$('context').onchange =
    () => {

        const showContext =
            $('context').checked;

        meshes.forEach(o => {

            o.visible =
                showContext ||
                isBridge(o);
        });

        clearHighlight();

        clearMeasurement();
    };

// ============================================================
// MEASUREMENT MODE
// ============================================================

$('measure').onclick =
    () => {

        measuring =
            !measuring;

        $('measure')
            .setAttribute(
                'aria-pressed',
                measuring
            );

        clearMeasurement();

        $('measure-result').textContent =
            measuring
                ?
                'Click two points on the model.'
                :
                '';
    };

// ============================================================
// POINTER / OBJECT SELECTION
// ============================================================

let down = null;

renderer.domElement
    .addEventListener(
        'pointerdown',
        e => {

            down = [
                e.clientX,
                e.clientY
            ];
        }
    );

renderer.domElement
    .addEventListener(
        'pointerup',
        e => {

            if (
                !root ||
                !down
            ) {

                return;
            }

            // Ignore drag/orbit operations.
            if (
                Math.hypot(
                    e.clientX - down[0],
                    e.clientY - down[1]
                ) > 5
            ) {

                return;
            }

            const rect =
                renderer.domElement
                    .getBoundingClientRect();

            const mouse =
                new THREE.Vector2(

                    (
                        e.clientX -
                        rect.left
                    )
                    /
                    rect.width
                    *
                    2
                    -
                    1,

                    -
                    (
                        e.clientY -
                        rect.top
                    )
                    /
                    rect.height
                    *
                    2
                    +
                    1
                );

            raycaster.setFromCamera(
                mouse,
                camera
            );

            const sensorHit =
                raycaster.intersectObjects(
                    sensorMarkerMeshes,
                    false
                )[0];

            if (sensorHit) {

                notifySensorSelection(sensorHit.object.userData.sensor);

                return;
            }

            const visibleMeshes =
                meshes.filter(
                    o =>
                        o.visible
                );

            const intersections =
                raycaster.intersectObjects(
                    visibleMeshes,
                    false
                );

            const hit =
                intersections[0];

            if (!hit) {
                return;
            }

            // =================================================
            // HIGHLIGHT SELECTED OBJECT
            // =================================================

            clearHighlight();

            highlight =
                new THREE.BoxHelper(
                    hit.object,
                    0x53e8ce
                );

            scene.add(
                highlight
            );

            // =================================================
            // OBJECT BOUNDING BOX / ELEVATION
            // =================================================

            const box =
                new THREE.Box3()
                    .setFromObject(
                        hit.object
                    );

            const minZ =
                box.min.z;

            const maxZ =
                box.max.z;

            const height =
                maxZ -
                minZ;

            const exportId =
                hit.object
                    .userData
                    .export_element_id
                ||
                'not supplied';

            $('selection').textContent =
                'Object: ' +
                hit.object.name
                +
                '\n'
                +
                'Export ID: ' +
                exportId
                +
                '\n'
                +
                'Min Z: ' +
                minZ.toFixed(3) +
                ' m'
                +
                '\n'
                +
                'Max Z: ' +
                maxZ.toFixed(3) +
                ' m'
                +
                '\n'
                +
                'Height: ' +
                height.toFixed(3) +
                ' m'
                +
                '\n'
                +
                'Bridge object: ' +
                (
                    isBridge(hit.object)
                        ?
                        'YES'
                        :
                        'NO'
                )
                +
                '\n'
                +
                'Sensor mapping: not assigned';

            // =================================================
            // MEASUREMENT
            // =================================================

            if (measuring) {

                if (
                    points.length ===
                    2
                ) {

                    clearMeasurement();
                }

                points.push(
                    hit.point.clone()
                );

                if (
                    points.length ===
                    1
                ) {

                    $('measure-result').textContent =
                        'First point selected. Click the second point.';

                    return;
                }

                if (
                    points.length ===
                    2
                ) {

                    const distance =
                        points[0]
                            .distanceTo(
                                points[1]
                            );

                    const geometry =
                        new THREE
                            .BufferGeometry()
                            .setFromPoints(
                                points
                            );

                    const material =
                        new THREE
                            .LineBasicMaterial({

                                color:
                                    0xffff66,

                                depthTest:
                                    false
                            });

                    line =
                        new THREE.Line(
                            geometry,
                            material
                        );

                    line.renderOrder =
                        5;

                    scene.add(
                        line
                    );

                    $('measure-result').textContent =
                        distance.toFixed(3) +
                        ' m · exported surface-point distance';
                }
            }
        }
    );

// ============================================================
// MODEL UPLOAD
// ============================================================

$('upload').onsubmit =
    async e => {

        e.preventDefault();

        const file =
            $('file').files[0];

        if (!file) {

            return;
        }

        // Only GLB files up to 100 MB.
        if (
            !file.name
                .toLowerCase()
                .endsWith('.glb')
            ||
            file.size >
                100 *
                1024 *
                1024
        ) {

            $('upload-status').textContent =
                'Choose a GLB smaller than 100 MB.';

            return;
        }

        $('upload-button').disabled =
            true;

        $('upload-status').textContent =
            'Uploading…';

        try {

            const name =
                $('name')
                    .value
                    .trim();

            const response =
                await fetch(

                    '/models?name=' +
                    encodeURIComponent(
                        name
                    ),

                    {
                        method:
                            'POST',

                        headers: {

                            'Content-Type':
                                'model/gltf-binary'
                        },

                        body:
                            file
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {

                throw Error(

                    typeof data.detail ===
                    'string'
                        ?
                        data.detail
                        :
                        'Upload rejected'
                );
            }

            await refresh(
                data.id
            );

            $('upload-status').textContent =
                'Version saved. Original versions retained.';
        }

        catch (e) {

            console.error(e);

            $('upload-status').textContent =
                e.message;
        }

        finally {

            $('upload-button').disabled =
                false;
        }
    };

// ============================================================
// RESIZE
// ============================================================

new ResizeObserver(
    () => {

        const rect =
            $('viewport')
                .getBoundingClientRect();

        camera.aspect =
            rect.width /
            Math.max(
                1,
                rect.height
            );

        camera.updateProjectionMatrix();

        renderer.setSize(
            rect.width,
            rect.height
        );
    }
)
.observe(
    $('viewport')
);

// ============================================================
// ANIMATION LOOP
// ============================================================

renderer.setAnimationLoop(
    () => {

        controls.update();

        positionSensorMarkerButtons();

        renderer.render(
            scene,
            camera
        );
    }
);

// ============================================================
// START
// ============================================================

refresh()
    .catch(
        e => {

            console.error(e);

            $('status').textContent =
                e.message;
        }
    );
