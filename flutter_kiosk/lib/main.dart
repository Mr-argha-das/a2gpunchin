import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  final cameras = await availableCameras();
  runApp(AttendanceKioskApp(cameras: cameras));
}

class AttendanceKioskApp extends StatelessWidget {
  const AttendanceKioskApp(
      {super.key, required this.cameras, this.enableFaceService = true});

  final List<CameraDescription> cameras;
  final bool enableFaceService;

  @override
  Widget build(BuildContext context) {
    const primary = Color(0xFF21185F);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'rMatrix',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: primary,
          brightness: Brightness.light,
        ),
        scaffoldBackgroundColor: const Color(0xFFF4F7FB),
        useMaterial3: true,
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(18)),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(18),
            borderSide: const BorderSide(color: Color(0xFFD8E0EF)),
          ),
        ),
      ),
      home: KioskShell(cameras: cameras, enableFaceService: enableFaceService),
    );
  }
}

enum KioskPage { scanner, enroll, settings }

class KioskShell extends StatefulWidget {
  const KioskShell(
      {super.key, required this.cameras, this.enableFaceService = true});

  final List<CameraDescription> cameras;
  final bool enableFaceService;

  @override
  State<KioskShell> createState() => _KioskShellState();
}

class _KioskShellState extends State<KioskShell> {
  final _baseUrlController =
      TextEditingController(text: 'http://192.168.1.32:8001');
  final _branchCodeController = TextEditingController(text: 'AHIT');
  final _pinController = TextEditingController(text: '1234');
  final _employeeCodeController = TextEditingController();
  final _tts = FlutterTts();
  final _audioRecorder = AudioRecorder();
  final List<Uint8List> _voiceSamples = [];

  CameraController? _camera;
  KioskApiClient? _client;
  KioskSession? _session;
  KioskPage _page = KioskPage.settings;
  bool _busy = false;
  String _message = 'Connect kiosk from settings.';
  String? _voicePrompt;

  @override
  void initState() {
    super.initState();
    _configureVoice();
    _restore();
    _initCamera();
  }

  Future<void> _configureVoice() async {
    await _tts.setLanguage('en-IN');
    await _tts.setSpeechRate(0.58);
    await _tts.setPitch(1.0);
    await _tts.awaitSpeakCompletion(true);
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrlController.text =
        prefs.getString('base_url') ?? _baseUrlController.text;
    _branchCodeController.text =
        prefs.getString('branch_code') ?? _branchCodeController.text;
    _pinController.text = prefs.getString('kiosk_pin') ?? _pinController.text;
    final hasSavedSetup = prefs.containsKey('base_url') &&
        prefs.containsKey('branch_code') &&
        prefs.containsKey('kiosk_pin');
    if (hasSavedSetup) {
      await _startKiosk(silent: true);
    }
  }

  Future<void> _initCamera() async {
    if (widget.cameras.isEmpty) {
      _setMessage('Camera not found on this device.');
      return;
    }
    final frontCamera = widget.cameras.firstWhere(
      (camera) => camera.lensDirection == CameraLensDirection.front,
      orElse: () => widget.cameras.first,
    );
    final controller = CameraController(frontCamera, ResolutionPreset.medium,
        enableAudio: false);
    await controller.initialize();
    if (!mounted) return;
    setState(() => _camera = controller);
  }

  void _setMessage(String message) {
    if (!mounted) return;
    setState(() => _message = message);
  }

  void _openPage(KioskPage page) {
    setState(() => _page = page);
  }

  String _normalizedBaseUrl() {
    final raw = _baseUrlController.text.trim();
    if (raw.isEmpty) {
      throw Exception('Enter backend URL first.');
    }
    final withScheme = raw.startsWith('http://') || raw.startsWith('https://')
        ? raw
        : 'http://$raw';
    return withScheme.replaceAll(RegExp(r'/+$'), '');
  }

  Future<void> _startKiosk({bool silent = false}) async {
    setState(() {
      _busy = true;
      _message = 'Connecting kiosk...';
    });
    try {
      final backendUrl = _normalizedBaseUrl();
      _baseUrlController.text = backendUrl;
      final client = KioskApiClient(baseUrl: backendUrl);
      final session = await client.login(
        branchCode: _branchCodeController.text.trim(),
        kioskPin: _pinController.text.trim(),
      );
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('base_url', backendUrl);
      await prefs.setString('branch_code', _branchCodeController.text.trim());
      await prefs.setString('kiosk_pin', _pinController.text.trim());
      setState(() {
        _client = client;
        _session = session;
        _page = KioskPage.scanner;
        _message = 'Ready at ${session.branchName}.';
      });
      if (!silent) {
        _toast('Kiosk ready at ${session.branchName}', success: true);
        await _speak('Kiosk ready');
      }
    } catch (error) {
      final message = _connectionErrorMessage(error);
      _toast(message, success: false);
      _setMessage(message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _connectionErrorMessage(Object error) {
    final text = error.toString();
    final normalized = text.toLowerCase();
    if (normalized.contains('clientexception') ||
        normalized.contains('connection closed') ||
        normalized.contains('connection refused') ||
        normalized.contains('failed host lookup') ||
        normalized.contains('network is unreachable')) {
      return 'Cannot connect to backend. Check that FastAPI is running, this phone is on the same Wi-Fi, and Backend URL uses the correct IP/port, for example http://192.168.1.32:8001.';
    }
    return text;
  }

  Future<Uint8List> _captureImageBytes() async {
    final camera = _camera;
    if (camera == null || !camera.value.isInitialized) {
      throw Exception('Camera is not ready.');
    }
    final file = await camera.takePicture();
    return File(file.path).readAsBytes();
  }

  Future<Uint8List> _recordVoiceClip({
    required String prompt,
    Duration duration = const Duration(milliseconds: 2500),
  }) async {
    if (!await _audioRecorder.hasPermission()) {
      throw Exception(
          'Microphone permission is required for voice attendance.');
    }
    await _tts.stop();
    await _speak(prompt);
    await Future.delayed(const Duration(milliseconds: 120));
    final directory = await getTemporaryDirectory();
    final path =
        '${directory.path}/voice_${DateTime.now().microsecondsSinceEpoch}.m4a';
    await _audioRecorder.start(
      const RecordConfig(
        encoder: AudioEncoder.aacLc,
        bitRate: 64000,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: path,
    );
    if (mounted) {
      setState(() {
        _voicePrompt = prompt;
        _message = prompt;
      });
    }
    await Future.delayed(duration);
    final recordedPath = await _audioRecorder.stop();
    if (recordedPath == null) {
      throw Exception('Voice recording failed.');
    }
    final file = File(recordedPath);
    final bytes = await file.readAsBytes();
    unawaited(file.delete().catchError((_) => file));
    return bytes;
  }

  Future<void> _scanAndPunch() async {
    if (_busy || _page != KioskPage.scanner) return;
    final client = _client;
    final session = _session;
    if (client == null || session == null) {
      _setMessage('Open Settings and start kiosk first.');
      return;
    }
    setState(() {
      _busy = true;
      _message = 'Scanning face...';
    });
    try {
      final imageBytes = await _captureImageBytes();
      setState(() => _message = 'Face matched. Preparing voice PIN...');
      final challengeResult = await client.faceVoiceChallenge(
        branchId: session.branchId,
        kioskPin: _pinController.text.trim(),
        action: 'auto',
        imageBytes: imageBytes,
      );
      final digits = challengeResult['digits']?.toString() ?? '';
      final instruction = digits.isEmpty ? 'Say the digits.' : 'Say $digits';
      final audioBytes = await _recordVoiceClip(
        prompt: instruction,
        duration: const Duration(milliseconds: 2500),
      );
      final result = await client.verifyFaceVoicePunch(
        branchId: session.branchId,
        kioskPin: _pinController.text.trim(),
        challengeId: challengeResult['challenge_id'].toString(),
        audioBytes: audioBytes,
      );
      final name = result['employee_name']?.toString() ?? 'Employee';
      final firstName = name.split(' ').first;
      final didPunchOut = result['action']?.toString() == 'punch_out';
      final message = didPunchOut
          ? 'Punch out successful. Thank you $firstName.'
          : 'Punch in successful. Thank you $firstName.';
      _toast(message, success: true);
      unawaited(_speak(message));
      if (mounted) {
        setState(() {
          _voicePrompt = null;
          _message = message;
        });
      }
    } catch (error) {
      final message = error.toString().replaceFirst('Exception: ', '');
      if (!message.toLowerCase().contains('no face')) {
        _toast(message, success: false);
      }
      if (mounted) {
        setState(() {
          _voicePrompt = null;
          _message = message;
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _captureVoiceSample() async {
    final employeeCode = _employeeCodeController.text.trim();
    if (employeeCode.isEmpty) {
      _toast('Enter employee code first.', success: false);
      return;
    }
    if (_voiceSamples.length >= 5) {
      _toast('Five voice samples are already ready.', success: true);
      return;
    }
    setState(() {
      _busy = true;
      _message = 'Preparing voice sample ${_voiceSamples.length + 1} of 5...';
    });
    try {
      final next = _voiceSamples.length + 1;
      final sample = await _recordVoiceClip(
        prompt: 'Voice sample $next. Say the digits 1 2 3 4 5 6 clearly.',
      );
      setState(() {
        _voiceSamples.add(sample);
        _voicePrompt = null;
        _message = 'Voice sample ${_voiceSamples.length} of 5 saved.';
      });
      _toast('Voice sample ${_voiceSamples.length}/5 saved', success: true);
    } catch (error) {
      final message = error.toString().replaceFirst('Exception: ', '');
      _toast(message, success: false);
      _setMessage(message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<List<Uint8List>> _recordEnrollmentSamples() async {
    final samples = List<Uint8List>.from(_voiceSamples);
    while (samples.length < 5) {
      final next = samples.length + 1;
      if (mounted) {
        setState(() {
          _message = 'Recording voice sample $next of 5...';
        });
      }
      final sample = await _recordVoiceClip(
        prompt: 'Voice sample $next. Say the digits 1 2 3 4 5 6 clearly.',
      );
      samples.add(sample);
      if (mounted) {
        setState(() {
          _voiceSamples
            ..clear()
            ..addAll(samples);
          _voicePrompt = null;
          _message = 'Voice sample $next of 5 saved.';
        });
      }
    }
    return samples;
  }

  void _clearVoiceSamples() {
    setState(() {
      _voiceSamples.clear();
      _voicePrompt = null;
      _message = 'Voice samples cleared.';
    });
  }

  Future<void> _enrollVoice() async {
    final client = _client;
    final session = _session;
    final employeeCode = _employeeCodeController.text.trim();
    if (employeeCode.isEmpty) {
      _toast('Enter employee code.', success: false);
      return;
    }
    if (client == null || session == null) {
      _toast('Start kiosk from settings first.', success: false);
      return;
    }
    setState(() {
      _busy = true;
      _message = _voiceSamples.length < 5
          ? 'Recording voice enrollment...'
          : 'Uploading voice enrollment...';
    });
    try {
      final samples = await _recordEnrollmentSamples();
      setState(() => _message = 'Uploading voice enrollment...');
      final result = await client.enrollVoice(
        branchId: session.branchId,
        kioskPin: _pinController.text.trim(),
        employeeCode: employeeCode,
        samples: samples,
      );
      final code = result['employee_code']?.toString() ?? employeeCode;
      setState(() {
        _voiceSamples.clear();
        _voicePrompt = null;
        _message = 'Voice enrolled for $code.';
      });
      _toast('Voice enrolled for $code', success: true);
      await _speak('Voice enrolled');
    } catch (error) {
      final message = error.toString().replaceFirst('Exception: ', '');
      _toast(message, success: false);
      _setMessage(message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _enrollFaceAndVoice() async {
    final client = _client;
    final session = _session;
    final employeeCode = _employeeCodeController.text.trim();
    if (employeeCode.isEmpty) {
      _toast('Enter employee code.', success: false);
      return;
    }
    if (client == null || session == null) {
      _toast('Start kiosk from settings first.', success: false);
      return;
    }
    setState(() {
      _busy = true;
      _message = 'Capturing face first...';
    });
    try {
      final imageBytes = await _captureImageBytes();
      final faceResult = await client.enrollFace(
        branchId: session.branchId,
        kioskPin: _pinController.text.trim(),
        employeeCode: employeeCode,
        imageBytes: imageBytes,
      );
      setState(() => _message = 'Face enrolled. Recording voice next...');
      final samples = await _recordEnrollmentSamples();
      setState(() => _message = 'Uploading voice enrollment...');
      final voiceResult = await client.enrollVoice(
        branchId: session.branchId,
        kioskPin: _pinController.text.trim(),
        employeeCode: employeeCode,
        samples: samples,
      );
      final name = faceResult['employee_name']?.toString() ??
          faceResult['name']?.toString() ??
          voiceResult['employee_code']?.toString() ??
          employeeCode;
      setState(() {
        _voiceSamples.clear();
        _voicePrompt = null;
        _message = 'Face and voice enrolled for $name.';
      });
      _toast('Face and voice enrolled for $name', success: true);
      await _speak('Face and voice enrolled');
    } catch (error) {
      final message = error.toString().replaceFirst('Exception: ', '');
      _toast(message, success: false);
      _setMessage(message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String message, {required bool success}) {
    Fluttertoast.showToast(
      msg: message,
      toastLength: Toast.LENGTH_LONG,
      gravity: ToastGravity.TOP,
      backgroundColor:
          success ? const Color(0xFF0F766E) : const Color(0xFFDC2626),
      textColor: Colors.white,
      fontSize: 16,
    );
  }

  Future<void> _speak(String message) async {
    await _tts.stop();
    await _tts.speak(message);
  }

  @override
  void dispose() {
    _camera?.dispose();
    _audioRecorder.dispose();
    _tts.stop();
    _baseUrlController.dispose();
    _branchCodeController.dispose();
    _pinController.dispose();
    _employeeCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= 760;
    return Scaffold(
      body: Row(
        children: [
          if (isWide) _Sidebar(state: this),
          Expanded(child: _pageBody()),
        ],
      ),
      bottomNavigationBar: isWide ? null : _BottomNav(state: this),
    );
  }

  Widget _pageBody() {
    return switch (_page) {
      KioskPage.scanner => _ScannerPage(state: this),
      KioskPage.enroll => _EnrollPage(state: this),
      KioskPage.settings => _SettingsPage(state: this),
    };
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 260,
      padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0B1020), Color(0xFF111846)],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14)),
                child: const Center(
                    child: Text('RM',
                        style: TextStyle(
                            fontWeight: FontWeight.w900,
                            color: Color(0xFF21185F)))),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('rMatrix',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.w900)),
                    Text('Face + voice console',
                        style:
                            TextStyle(color: Color(0xFFAAB2D5), fontSize: 12)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 28),
          _NavItem(
              icon: Icons.face_retouching_natural,
              label: 'Punch Scanner',
              selected: state._page == KioskPage.scanner,
              onTap: () => state._openPage(KioskPage.scanner)),
          _NavItem(
              icon: Icons.person_add_alt_1,
              label: 'Enroll Face + Voice',
              selected: state._page == KioskPage.enroll,
              onTap: () => state._openPage(KioskPage.enroll)),
          _NavItem(
              icon: Icons.settings,
              label: 'Settings',
              selected: state._page == KioskPage.settings,
              onTap: () => state._openPage(KioskPage.settings)),
          const Spacer(),
          _StatusPill(session: state._session),
        ],
      ),
    );
  }
}

class _BottomNav extends StatelessWidget {
  const _BottomNav({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: state._page.index,
      onDestinationSelected: (index) =>
          state._openPage(KioskPage.values[index]),
      destinations: const [
        NavigationDestination(
            icon: Icon(Icons.face_retouching_natural), label: 'Punch'),
        NavigationDestination(
            icon: Icon(Icons.person_add_alt_1), label: 'Enroll'),
        NavigationDestination(icon: Icon(Icons.settings), label: 'Settings'),
      ],
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem(
      {required this.icon,
      required this.label,
      required this.selected,
      required this.onTap});

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          decoration: BoxDecoration(
            color: selected ? const Color(0xFF1C2553) : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
            border: selected
                ? const Border(
                    left: BorderSide(color: Color(0xFF7DD3FC), width: 4))
                : null,
          ),
          child: Row(
            children: [
              Icon(icon, color: Colors.white, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.session});

  final KioskSession? session;

  @override
  Widget build(BuildContext context) {
    final ready = session != null;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: ready
            ? const Color(0xFFECFDF5)
            : Colors.white.withValues(alpha: .08),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Text(
        ready ? 'Ready at ${session!.branchName}' : 'Kiosk not started',
        style: TextStyle(
            color: ready ? const Color(0xFF047857) : Colors.white,
            fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _ScannerPage extends StatelessWidget {
  const _ScannerPage({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    final camera = state._camera;
    return Stack(
      fit: StackFit.expand,
      children: [
        if (camera != null && camera.value.isInitialized)
          FittedBox(
            fit: BoxFit.cover,
            child: SizedBox(
              width: camera.value.previewSize?.height ?? 1080,
              height: camera.value.previewSize?.width ?? 1920,
              child: CameraPreview(camera),
            ),
          )
        else
          const ColoredBox(
            color: Color(0xFF0B1020),
            child:
                Center(child: CircularProgressIndicator(color: Colors.white)),
          ),
        const _ScannerScrim(),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    _GlassChip(
                        icon: Icons.apartment,
                        label: state._session?.branchName ??
                            'Start kiosk from settings'),
                    const Spacer(),
                    const _GlassChip(
                        icon: Icons.touch_app, label: 'Manual Start'),
                  ],
                ),
                const Spacer(),
                Center(
                  child: Container(
                    width: 270,
                    height: 330,
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.white, width: 3),
                      borderRadius: BorderRadius.circular(150),
                    ),
                    child: const Align(
                      alignment: Alignment.bottomCenter,
                      child: Padding(
                        padding: EdgeInsets.only(bottom: 24),
                        child: Text('Place face here',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 20,
                                fontWeight: FontWeight.w900)),
                      ),
                    ),
                  ),
                ),
                if (state._voicePrompt != null) ...[
                  const SizedBox(height: 14),
                  Center(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 18, vertical: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFECFDF5),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: const Color(0xFF10B981)),
                      ),
                      child: Text(
                        state._voicePrompt!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Color(0xFF065F46),
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
                ],
                const Spacer(),
                SizedBox(
                  height: 58,
                  child: FilledButton.icon(
                    onPressed: state._busy ? null : state._scanAndPunch,
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text(
                      'Start Punch',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                _MessageBanner(message: state._message, busy: state._busy),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _ScannerScrim extends StatelessWidget {
  const _ScannerScrim();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            Colors.black.withValues(alpha: .62),
            Colors.transparent,
            Colors.black.withValues(alpha: .7)
          ],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
    );
  }
}

class _GlassChip extends StatelessWidget {
  const _GlassChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: .36),
          borderRadius: BorderRadius.circular(999)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: Colors.white, size: 18),
          const SizedBox(width: 8),
          Text(label,
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _MessageBanner extends StatelessWidget {
  const _MessageBanner({required this.message, required this.busy});

  final String message;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(22),
          boxShadow: const [
            BoxShadow(color: Color(0x33000000), blurRadius: 30)
          ]),
      child: Row(
        children: [
          if (busy) ...[
            const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 3)),
            const SizedBox(width: 12),
          ] else ...[
            const Icon(Icons.center_focus_strong, color: Color(0xFF21185F)),
            const SizedBox(width: 12),
          ],
          Expanded(
              child: Text(message,
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w800))),
        ],
      ),
    );
  }
}

class _EnrollPage extends StatelessWidget {
  const _EnrollPage({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    final camera = state._camera;
    return _PageScaffold(
      title: 'Enroll Face + Voice',
      subtitle:
          'Tap once to enroll face first, then record voice. Punches require face match and spoken PIN digits.',
      child: LayoutBuilder(
        builder: (context, constraints) {
          final isCompact = constraints.maxWidth < 720;
          if (isCompact) {
            return SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SizedBox(
                      height: 420,
                      child: _CameraCard(
                          camera: camera,
                          hint: 'Ask employee to look straight')),
                  const SizedBox(height: 16),
                  _EnrollFormCard(state: state),
                ],
              ),
            );
          }
          return Row(
            children: [
              Expanded(
                flex: 5,
                child: _CameraCard(
                    camera: camera, hint: 'Ask employee to look straight'),
              ),
              const SizedBox(width: 18),
              Expanded(flex: 4, child: _EnrollFormCard(state: state)),
            ],
          );
        },
      ),
    );
  }
}

class _EnrollFormCard extends StatelessWidget {
  const _EnrollFormCard({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    return _SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Employee Enrollment',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          Text('Enter employee code, then start face and voice enrollment.',
              style: TextStyle(color: Colors.grey.shade700, height: 1.35)),
          const SizedBox(height: 22),
          TextField(
            controller: state._employeeCodeController,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(
                labelText: 'Employee Code',
                prefixIcon: Icon(Icons.badge_outlined)),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 52,
                  child: OutlinedButton.icon(
                    onPressed: state._busy ? null : state._captureVoiceSample,
                    icon: const Icon(Icons.mic),
                    label: FittedBox(
                      fit: BoxFit.scaleDown,
                      child:
                          Text('Voice Sample ${state._voiceSamples.length}/5'),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                onPressed: state._busy || state._voiceSamples.isEmpty
                    ? null
                    : state._clearVoiceSamples,
                icon: const Icon(Icons.refresh),
                tooltip: 'Clear voice samples',
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              onPressed: state._busy ? null : state._enrollFaceAndVoice,
              icon: const Icon(Icons.verified_user),
              label: const FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text('Start Face + Voice Enrollment')),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 48,
            child: OutlinedButton.icon(
              onPressed: state._busy ? null : state._enrollVoice,
              icon: const Icon(Icons.record_voice_over),
              label: const FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text('Voice Only (Face Exists)')),
            ),
          ),
          if (state._voicePrompt != null) ...[
            const SizedBox(height: 12),
            Text(state._voicePrompt!,
                style: const TextStyle(
                    color: Color(0xFF065F46),
                    fontWeight: FontWeight.w900,
                    height: 1.35)),
          ],
          const SizedBox(height: 16),
          Text(state._message,
              style:
                  const TextStyle(fontWeight: FontWeight.w700, height: 1.35)),
        ],
      ),
    );
  }
}

class _SettingsPage extends StatelessWidget {
  const _SettingsPage({required this.state});

  final _KioskShellState state;

  @override
  Widget build(BuildContext context) {
    return _PageScaffold(
      title: 'Kiosk Settings',
      subtitle:
          'Start this TL phone from its kiosk branch. Employees assigned to this branch can punch after face and voice enrollment.',
      child: SingleChildScrollView(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: _SurfaceCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Connection',
                      style:
                          TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
                  const SizedBox(height: 18),
                  TextField(
                    controller: state._baseUrlController,
                    keyboardType: TextInputType.url,
                    textInputAction: TextInputAction.next,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration: const InputDecoration(
                      labelText: 'Backend URL',
                      hintText: 'http://192.168.1.10:8001',
                      helperText:
                          'Use your server IP and port. http:// is added automatically if missing.',
                      prefixIcon: Icon(Icons.link),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                      controller: state._branchCodeController,
                      decoration: const InputDecoration(
                          labelText: 'Branch Code',
                          prefixIcon: Icon(Icons.apartment))),
                  const SizedBox(height: 12),
                  TextField(
                      controller: state._pinController,
                      obscureText: true,
                      decoration: const InputDecoration(
                          labelText: 'Kiosk PIN', prefixIcon: Icon(Icons.pin))),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: state._busy ? null : state._startKiosk,
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text('Start Kiosk'),
                  ),
                  const SizedBox(height: 14),
                  Text(state._message,
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PageScaffold extends StatelessWidget {
  const _PageScaffold(
      {required this.title, required this.subtitle, required this.child});

  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < 520;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.all(compact ? 20 : 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title,
                style: TextStyle(
                    fontSize: compact ? 28 : 32, fontWeight: FontWeight.w900)),
            const SizedBox(height: 6),
            Text(subtitle,
                style: TextStyle(
                    color: Colors.grey.shade700,
                    fontWeight: FontWeight.w600,
                    height: 1.35)),
            SizedBox(height: compact ? 18 : 22),
            Expanded(child: child),
          ],
        ),
      ),
    );
  }
}

class _SurfaceCard extends StatelessWidget {
  const _SurfaceCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < 520;
    return Container(
      padding: EdgeInsets.all(compact ? 20 : 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(compact ? 22 : 28),
        border: Border.all(color: const Color(0xFFD8E0EF)),
        boxShadow: const [
          BoxShadow(
              color: Color(0x110F172A), blurRadius: 28, offset: Offset(0, 18))
        ],
      ),
      child: child,
    );
  }
}

class _CameraCard extends StatelessWidget {
  const _CameraCard({required this.camera, required this.hint});

  final CameraController? camera;
  final String hint;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(28),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final ovalWidth = constraints.maxWidth.clamp(190.0, 250.0);
          final ovalHeight = (constraints.maxHeight * .62).clamp(230.0, 320.0);
          return Stack(
            fit: StackFit.expand,
            children: [
              if (camera != null && camera!.value.isInitialized)
                FittedBox(
                  fit: BoxFit.cover,
                  child: SizedBox(
                    width: camera!.value.previewSize?.height ?? 1080,
                    height: camera!.value.previewSize?.width ?? 1920,
                    child: CameraPreview(camera!),
                  ),
                )
              else
                const ColoredBox(
                  color: Color(0xFF0B1020),
                  child: Center(
                      child: CircularProgressIndicator(color: Colors.white)),
                ),
              DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.transparent,
                      Colors.black.withValues(alpha: .72)
                    ],
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                  ),
                ),
              ),
              Center(
                child: Container(
                  width: ovalWidth,
                  height: ovalHeight,
                  decoration: BoxDecoration(
                      border: Border.all(color: Colors.white, width: 3),
                      borderRadius: BorderRadius.circular(160)),
                ),
              ),
              Positioned(
                left: 18,
                right: 18,
                bottom: 18,
                child: Text(hint,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                        height: 1.25)),
              ),
            ],
          );
        },
      ),
    );
  }
}
