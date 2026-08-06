# Redis 연결 문제 해결을 위한 Runbook

## 📌 Overview

Redis 서버와의 연결 문제로 인해 `Connection pool exhausted` 오류가 발생했습니다. 이는 애플리케이션이 Redis와의 연결을 유지하지 못하고, 연결 풀이 고갈되어 발생한 문제입니다.

## 🔍 Root Cause

Redis 연결 문제의 근본 원인은 서버 방화벽이 유휴 연결(Idle Connection)을 300초마다 강제로 끊어버린 것입니다. 결과적으로 연결 풀이 고갈되었고, 애플리케이션은 새로운 연결을 생성할 수 없어 `Connection pool exhausted`라는 오류를 발생시켰습니다.

## 🛠 Resolution Steps

문제를 해결하기 위해 다음과 같은 조치를 취했습니다:

1. **TCP Keepalive 활성화**: 유휴 연결 유지 시간을 늘리기 위해 서버 측에서 TCP Keepalive를 활성화합니다.

2. **Redis-Py 클라이언트에서 주기적 연결 상태 확인 설정**:
   - `redis-py` 클라이언트 설정에 `health_check_interval=30` 옵션을 추가하여 주기적으로 연결 상태를 점검하고 유지합니다. 이를 통해 방화벽에 의해 연결이 끊어지기 전에 주기적으로 연결을 유지할 수 있습니다.

### 예시 코드 스니펫

```python
import redis

# Redis 연결 생성 시 health_check_interval 옵션 설정
client = redis.Redis(
    host='your_redis_host',
    port=6379,
    password='your_password',
    health_check_interval=30  # 30초 간격으로 연결 상태 점검
)

# Redis 명령 실행
try:
    client.ping()
    print("Redis connection is stable.")
except redis.ConnectionError:
    print("Failed to connect to Redis.")
```

3. **방화벽 설정 조정**: 향후 유사한 문제가 발생하지 않도록 서버 방화벽 설정을 검토하여 유휴 연결 유지 시간을 늘리거나 TCP Keepalive 설정을 강화합니다.

## ⚠️ Caveats

- **서버 인프라의 방화벽 정책 검토**: 방화벽의 유휴 연결 시간 정책이 서버 성능에 영향을 미칠 수 있으므로, 적절히 조정해야 합니다.
  
- **지속적인 로그 모니터링**: Redis 연결 문제에 대한 로그를 지속적으로 모니터링하여 `health_check_interval` 또는 기타 설정이 적절히 작동하는지 확인합니다.

- **클라이언트 설정 테스트**: 클라이언트 측에서 설정 변화를 테스트하고 미치는 영향을 분석해야 합니다. 필요한 경우 `health_check_interval` 값을 조정하여 애플리케이션과 서버의 특성에 맞게 최적화해야 합니다.