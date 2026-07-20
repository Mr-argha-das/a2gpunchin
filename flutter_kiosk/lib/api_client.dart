import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

class KioskSession {
  KioskSession({
    required this.branchId,
    required this.branchName,
    required this.tenantId,
    this.companyId,
  });

  final String branchId;
  final String branchName;
  final String tenantId;
  final String? companyId;

  factory KioskSession.fromJson(Map<String, dynamic> json) => KioskSession(
        branchId: json['branch_id'] as String,
        branchName: json['branch_name'] as String,
        tenantId: json['tenant_id'] as String,
        companyId: json['company_id'] as String?,
      );
}

class KioskEmployeeOption {
  KioskEmployeeOption({
    required this.employeeId,
    required this.employeeCode,
    required this.employeeName,
    this.department,
    required this.faceEnrolled,
  });

  final String employeeId;
  final String employeeCode;
  final String employeeName;
  final String? department;
  final bool faceEnrolled;

  String get label => '$employeeCode - $employeeName';

  factory KioskEmployeeOption.fromJson(Map<String, dynamic> json) =>
      KioskEmployeeOption(
        employeeId: json['employee_id']?.toString() ?? '',
        employeeCode: json['employee_code']?.toString() ?? '',
        employeeName: json['employee_name']?.toString() ?? '',
        department: json['department']?.toString(),
        faceEnrolled: json['face_enrolled'] == true,
      );
}

class KioskApiClient {
  KioskApiClient({required this.baseUrl});

  final String baseUrl;

  Uri _uri(String path) {
    final base = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    if (base.endsWith('/api') && path.startsWith('/api/')) {
      return Uri.parse('$base${path.substring(4)}');
    }
    return Uri.parse('$base$path');
  }

  Future<KioskSession> login({
    required String branchCode,
    required String kioskPin,
  }) async {
    final response = await http.post(
      _uri('/api/kiosk/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'branch_code': branchCode, 'kiosk_pin': kioskPin}),
    );
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return KioskSession.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> faceVoiceChallenge({
    required String branchId,
    required String kioskPin,
    required String action,
    required Uint8List imageBytes,
  }) async {
    final request =
        http.MultipartRequest('POST', _uri('/api/v1/face-voice/challenge'))
          ..fields['branch_id'] = branchId
          ..fields['kiosk_pin'] = kioskPin
          ..fields['action'] = action
          ..files.add(http.MultipartFile.fromBytes(
            'image',
            imageBytes,
            filename: 'challenge.jpg',
            contentType: MediaType('image', 'jpeg'),
          ));
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> livenessConfig() async {
    final response = await http.get(_uri('/api/v1/face-voice/liveness-config'));
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> secureFaceVoiceChallenge({
    required String branchId,
    required String kioskPin,
    required String action,
    required Uint8List imageBytes,
    required List<Uint8List> frameBytes,
    required Map<String, dynamic> livenessMetadata,
  }) async {
    final request = http.MultipartRequest(
        'POST', _uri('/api/v1/face-voice/secure-challenge'))
      ..fields['branch_id'] = branchId
      ..fields['kiosk_pin'] = kioskPin
      ..fields['action'] = action
      ..fields['liveness_metadata'] = jsonEncode(livenessMetadata)
      ..files.add(http.MultipartFile.fromBytes(
        'image',
        imageBytes,
        filename: 'recognition.jpg',
        contentType: MediaType('image', 'jpeg'),
      ));
    for (var index = 0; index < frameBytes.length; index += 1) {
      request.files.add(http.MultipartFile.fromBytes(
        'frames',
        frameBytes[index],
        filename: 'liveness_$index.jpg',
        contentType: MediaType('image', 'jpeg'),
      ));
    }
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> verifyFaceVoicePunch({
    required String branchId,
    required String kioskPin,
    required String challengeId,
    required Uint8List audioBytes,
  }) async {
    final request =
        http.MultipartRequest('POST', _uri('/api/v1/face-voice/verify'))
          ..fields['branch_id'] = branchId
          ..fields['kiosk_pin'] = kioskPin
          ..fields['challenge_id'] = challengeId
          ..files.add(http.MultipartFile.fromBytes(
            'audio',
            audioBytes,
            filename: 'digits.m4a',
            contentType: MediaType('audio', 'mp4'),
          ));
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> enrollFace({
    required String branchId,
    required String kioskPin,
    required String employeeCode,
    required Uint8List imageBytes,
  }) async {
    final request =
        http.MultipartRequest('POST', _uri('/api/v1/attendance/employees'))
          ..fields['employee_id'] = employeeCode
          ..fields['name'] = employeeCode
          ..fields['branch_id'] = branchId
          ..fields['kiosk_pin'] = kioskPin
          ..files.add(http.MultipartFile.fromBytes(
            'image',
            imageBytes,
            filename: '$employeeCode.jpg',
            contentType: MediaType('image', 'jpeg'),
          ));
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> enrollVoice({
    required String branchId,
    required String kioskPin,
    required String employeeCode,
    required List<Uint8List> samples,
  }) async {
    final request =
        http.MultipartRequest('POST', _uri('/api/v1/face-voice/enroll'))
          ..fields['employee_code'] = employeeCode
          ..fields['branch_id'] = branchId
          ..fields['kiosk_pin'] = kioskPin;
    for (var index = 0; index < samples.length; index += 1) {
      request.files.add(http.MultipartFile.fromBytes(
        'samples',
        samples[index],
        filename: 'voice_sample_${index + 1}.m4a',
        contentType: MediaType('audio', 'mp4'),
      ));
    }
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<KioskEmployeeOption>> searchEmployees({
    required String branchId,
    required String kioskPin,
    String search = '',
  }) async {
    final uri = _uri('/api/v1/attendance/employees/search').replace(
      queryParameters: {
        'branch_id': branchId,
        'kiosk_pin': kioskPin,
        'search': search,
        'limit': '500',
      },
    );
    final response = await http.get(uri);
    if (response.statusCode != 200) {
      throw Exception(_detail(response));
    }
    final body = jsonDecode(response.body) as List<dynamic>;
    return body
        .map((item) =>
            KioskEmployeeOption.fromJson(item as Map<String, dynamic>))
        .where((item) => item.employeeCode.isNotEmpty)
        .toList();
  }

  String _detail(http.Response response) {
    final contentType = response.headers['content-type'] ?? '';
    final bodyText = response.body.trim();
    if (contentType.contains('text/html') ||
        bodyText.startsWith('<!doctype html') ||
        bodyText.startsWith('<html')) {
      return 'Backend returned a web page instead of API JSON. Check Backend URL, port, and make sure the FastAPI server is running.';
    }
    try {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      return body['detail']?.toString() ?? response.body;
    } catch (_) {
      if (bodyText.length > 180) {
        return '${bodyText.substring(0, 180)}...';
      }
      return bodyText.isEmpty
          ? 'Request failed with status ${response.statusCode}'
          : bodyText;
    }
  }
}
