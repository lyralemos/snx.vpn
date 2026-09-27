import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
    id: root

    moduleName: "snx.vpn"

    property bool connected: false
    property string tunnelIp: ""
    property string activeConnectionId: ""
    property var connections: []
    property bool busy: false
    property string statusMessage: ""
    property string errorMessage: ""

    // Form states for adding / editing connection
    property bool showAddForm: false
    property string editingId: ""
    property string newName: ""
    property string newHost: ""
    property string newUser: ""
    property string newPassword: ""

    // Password modal state for connecting if password isn't saved
    property string promptConnId: ""
    property string promptConnName: ""
    property string promptPassword: ""

    readonly property string helperScript: Qt.resolvedUrl("snx_service.py").toString().replace(/^file:\/\//, "")

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function outputIcon() {
        if (root.connected) return ""
        return ""
    }

    function refresh() {
        if (!statusProc.running) {
            statusProc.command = [root.helperScript, "status"]
            statusProc.running = true
        }
    }

    function connectVPN(connId) {
        if (root.busy) return
        root.busy = true
        root.errorMessage = ""
        root.statusMessage = "Connecting..."
        var cmd = [root.helperScript, "connect", connId]
        actionProc.command = cmd
        actionProc.running = true
    }

    function disconnectVPN() {
        if (root.busy) return
        root.busy = true
        root.errorMessage = ""
        root.statusMessage = "Disconnecting..."
        actionProc.command = [root.helperScript, "disconnect"]
        actionProc.running = true
    }

    function removeVPN(connId) {
        if (root.busy) return
        root.busy = true
        actionProc.command = [root.helperScript, "remove", connId]
        actionProc.running = true
    }

    function startEditVPN(conn) {
        root.editingId = conn.id
        root.newName = conn.name || conn.id
        root.newHost = conn.server || ""
        root.newUser = conn.username || ""
        root.newPassword = ""
        root.showAddForm = true
        root.errorMessage = ""
    }

    function saveVPN() {
        if (!root.newName.trim() || !root.newHost.trim() || !root.newUser.trim()) {
            root.errorMessage = "Please fill in Name, Host, and Username."
            return
        }
        root.busy = true
        var cmd = []
        if (root.editingId) {
            cmd = [root.helperScript, "edit", root.editingId, root.newName.trim(), root.newHost.trim(), root.newUser.trim()]
        } else {
            cmd = [root.helperScript, "add", root.newName.trim(), root.newHost.trim(), root.newUser.trim()]
        }
        if (root.newPassword) {
            cmd.push(root.newPassword)
        }
        actionProc.command = cmd
        actionProc.running = true

        root.editingId = ""
        root.newName = ""
        root.newHost = ""
        root.newUser = ""
        root.newPassword = ""
        root.showAddForm = false
    }

    function cancelForm() {
        root.editingId = ""
        root.newName = ""
        root.newHost = ""
        root.newUser = ""
        root.newPassword = ""
        root.showAddForm = false
        root.errorMessage = ""
    }

    function parseJsonSafe(text) {
        try {
            return JSON.parse(text)
        } catch (e) {
            return null
        }
    }

    Component.onCompleted: {
        refresh()
    }

    Timer {
        interval: 8000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    Process {
        id: statusProc
        command: []
        stdout: StdioCollector {
            id: statusStdout
            waitForEnd: true
        }
        onExited: function(exitCode) {
            var data = root.parseJsonSafe(statusStdout.text)
            if (data) {
                root.connected = data.connected === true
                root.tunnelIp = data.tunnelIp || ""
                root.activeConnectionId = data.activeConnectionId || ""
                root.connections = data.connections || []
            }
        }
    }

    Process {
        id: actionProc
        command: []
        stdout: StdioCollector {
            id: actionStdout
            waitForEnd: true
        }
        stderr: StdioCollector {
            id: actionStderr
            waitForEnd: true
        }
        onExited: function(exitCode) {
            root.busy = false
            var data = root.parseJsonSafe(actionStdout.text)
            if (data) {
                if (data.needsPassword) {
                    root.promptConnId = data.id || ""
                    root.errorMessage = data.error || "Password required"
                } else if (!data.success && data.error) {
                    root.errorMessage = data.error
                    root.statusMessage = ""
                } else {
                    root.errorMessage = ""
                    root.statusMessage = data.message || ""
                }
            } else if (exitCode !== 0) {
                root.errorMessage = actionStderr.text || actionStdout.text || "Failed to perform action"
                root.statusMessage = ""
            }
            root.refresh()
        }
    }

    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        fontFamily: "omarchy"
        text: root.outputIcon()
        onPressed: function(b) {
            root.toggle()
        }
    }

    KeyboardPanel {
        id: panel
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.opened

        contentWidth: panel.fittedContentWidth(Style.space(380))
        contentHeight: panel.fittedContentHeight(panelColumn.implicitHeight, Style.space(560))

        ScrollView {
            id: scrollArea
            anchors.fill: parent
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical.policy: panelColumn.implicitHeight > height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff

            Column {
                id: panelColumn
                width: scrollArea.availableWidth
                spacing: Style.space(14)

                // Header
                Row {
                    width: parent.width
                    spacing: Style.space(10)

                    Text {
                        text: root.outputIcon()
                        color: root.bar ? root.bar.foreground : "#ffffff"
                        font.family: "omarchy"
                        font.pixelSize: Style.font.display
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - Style.space(50)

                        Text {
                            text: "Check Point SNX VPN"
                            color: root.bar ? root.bar.foreground : "#ffffff"
                            font.family: root.bar ? root.bar.fontFamily : "Sans"
                            font.pixelSize: Style.font.title
                            font.bold: true
                        }

                        Text {
                            text: root.connected
                                ? (root.tunnelIp ? "Connected (" + root.tunnelIp + ")" : "Connected")
                                : "Disconnected"
                            color: root.connected ? "#4caf50" : Qt.darker(root.bar ? root.bar.foreground : "#ffffff", 1.4)
                            font.family: root.bar ? root.bar.fontFamily : "Sans"
                            font.pixelSize: Style.font.caption
                            font.bold: true
                        }
                    }
                }

                // Error / Status Messages
                Text {
                    width: parent.width
                    text: root.errorMessage
                    visible: root.errorMessage !== ""
                    color: "#f44336"
                    font.family: root.bar ? root.bar.fontFamily : "Sans"
                    font.pixelSize: Style.font.caption
                    wrapMode: Text.WordWrap
                }

                Text {
                    width: parent.width
                    text: root.statusMessage
                    visible: root.statusMessage !== "" && root.errorMessage === ""
                    color: root.bar ? root.bar.foreground : "#ffffff"
                    font.family: root.bar ? root.bar.fontFamily : "Sans"
                    font.pixelSize: Style.font.caption
                    wrapMode: Text.WordWrap
                }

                PanelSeparator {
                    width: parent.width
                    foreground: root.bar ? root.bar.foreground : "#ffffff"
                }

                // Connections List Header
                Item {
                    width: parent.width
                    implicitHeight: Math.max(conectionLabel.implicitHeight, addBtn.implicitHeight)

                    Text {
                        id: conectionLabel
                        width: parent.width
                        text: "Saved Connections"
                        color: root.bar ? root.bar.foreground : "#ffffff"
                        font.family: root.bar ? root.bar.fontFamily : "Sans"
                        font.pixelSize: Style.font.caption
                        font.bold: true
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Button {
                        id: addBtn
                        text: root.showAddForm ? "Cancel" : "+ New"
                        implicitHeight: Style.space(28)
                        anchors.right: parent.right
                        onClicked: {
                            if (root.showAddForm) {
                                root.cancelForm()
                            } else {
                                root.editingId = ""
                                root.newName = ""
                                root.newHost = ""
                                root.newUser = ""
                                root.newPassword = ""
                                root.showAddForm = true
                                root.errorMessage = ""
                            }
                        }
                    }
                }

                // Add / Edit Connection Form
                Rectangle {
                    width: parent.width
                    implicitHeight: addCol.implicitHeight + Style.space(16)
                    visible: root.showAddForm
                    color: Qt.rgba(1, 1, 1, 0.05)
                    radius: Style.space(6)

                    Column {
                        id: addCol
                        anchors.fill: parent
                        anchors.margins: Style.space(8)
                        spacing: Style.space(6)

                        Text {
                            text: root.editingId ? "Edit Connection" : "New Connection"
                            color: root.bar ? root.bar.foreground : "#ffffff"
                            font.bold: true
                            font.pixelSize: Style.font.caption
                        }

                        TextField {
                            width: parent.width
                            placeholderText: "Name (e.g., Work)"
                            text: root.newName
                            onTextChanged: root.newName = text
                        }

                        TextField {
                            width: parent.width
                            placeholderText: "Host / Server (e.g., vpn.company.com)"
                            text: root.newHost
                            onTextChanged: root.newHost = text
                        }

                        TextField {
                            width: parent.width
                            placeholderText: "Username (e.g., john)"
                            text: root.newUser
                            onTextChanged: root.newUser = text
                        }

                        TextField {
                            width: parent.width
                            placeholderText: root.editingId ? "New Password (leave empty to keep current)" : "Password (stored in secret-tool, optional)"
                            echoMode: TextInput.Password
                            text: root.newPassword
                            onTextChanged: root.newPassword = text
                        }

                        Row {
                            width: parent.width
                            spacing: Style.space(6)

                            Button {
                                width: (parent.width - Style.space(6)) / 2
                                text: root.editingId ? "Update" : "Save"
                                enabled: !root.busy
                                onClicked: root.saveVPN()
                            }

                            Button {
                                width: (parent.width - Style.space(6)) / 2
                                text: "Cancel"
                                enabled: !root.busy
                                onClicked: root.cancelForm()
                            }
                        }
                    }
                }

                // Empty connections state
                Text {
                    width: parent.width
                    visible: root.connections.length === 0 && !root.showAddForm
                    text: "No connections found in ~/.config/snx/.\nClick '+ New' to add one."
                    color: Qt.darker(root.bar ? root.bar.foreground : "#ffffff", 1.5)
                    font.pixelSize: Style.font.caption
                    horizontalAlignment: Text.AlignHCenter
                }

                // List of saved connections
                Repeater {
                    model: root.connections

                    delegate: Rectangle {
                        required property var modelData
                        required property int index

                        width: parent.width
                        implicitHeight: itemCol.implicitHeight + Style.space(16)
                        color: (root.activeConnectionId === modelData.id && root.connected)
                            ? Qt.rgba(0.2, 0.6, 0.2, 0.2)
                            : Qt.rgba(1, 1, 1, 0.03)
                        radius: Style.space(6)
                        border.color: (root.activeConnectionId === modelData.id && root.connected)
                            ? "#4caf50"
                            : Qt.rgba(1, 1, 1, 0.1)
                        border.width: 1

                        Column {
                            id: itemCol
                            anchors.fill: parent
                            anchors.margins: Style.space(8)
                            spacing: Style.space(6)

                            Row {
                                width: parent.width
                                spacing: Style.space(6)

                                Column {
                                    width: parent.width - actionRow.implicitWidth - Style.space(6)

                                    Text {
                                        text: modelData.name || modelData.id
                                        color: root.bar ? root.bar.foreground : "#ffffff"
                                        font.bold: true
                                        font.pixelSize: Style.font.body
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }

                                    Text {
                                        text: (modelData.username ? modelData.username + "@" : "") + modelData.server
                                        color: Qt.darker(root.bar ? root.bar.foreground : "#ffffff", 1.4)
                                        font.pixelSize: Style.font.caption
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                }

                                Row {
                                    id: actionRow
                                    spacing: Style.space(6)
                                    anchors.verticalCenter: parent.verticalCenter

                                    Button {
                                        implicitHeight: Style.space(30)
                                        text: (root.connected && root.activeConnectionId === modelData.id) ? "Disconnect" : "Connect"
                                        enabled: !root.busy
                                        onClicked: {
                                            if (root.connected && root.activeConnectionId === modelData.id) {
                                                root.disconnectVPN()
                                            } else {
                                                root.connectVPN(modelData.id)
                                            }
                                        }
                                    }

                                    Button {
                                        implicitHeight: Style.space(30)
                                        text: "✎"
                                        enabled: !root.busy
                                        onClicked: {
                                            root.startEditVPN(modelData)
                                        }
                                    }

                                    Button {
                                        implicitHeight: Style.space(30)
                                        text: "✕"
                                        enabled: !root.busy && !(root.connected && root.activeConnectionId === modelData.id)
                                        onClicked: {
                                            root.removeVPN(modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}