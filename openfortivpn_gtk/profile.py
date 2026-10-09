"""
VPN Profile Model - Data structure for VPN connection profiles
"""

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List


@dataclass
class VPNProfile:
    """Represents a VPN connection profile."""
    
    name: str = "Nova Conexão"
    host: str = ""
    port: int = 443
    username: str = ""
    password: str = ""  # Note: In production, use libsecret
    realm: str = ""
    trusted_cert: str = ""
    set_routes: bool = True
    set_dns: bool = True
    use_syslog: bool = False
    half_internet_routes: bool = False
    user_cert: str = ""
    user_key: str = ""
    otp: str = ""
    
    # Unique identifier
    id: str = field(default_factory=lambda: "")
    
    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VPNProfile':
        """Create profile from dictionary."""
        if not isinstance(data, dict):
            raise ValueError("Perfil inválido")
        # Filter out unknown keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        text_fields = ('name', 'host', 'username', 'password', 'realm',
                       'trusted_cert', 'user_cert', 'user_key', 'otp', 'id')
        bool_fields = ('set_routes', 'set_dns', 'use_syslog', 'half_internet_routes')
        if any(key in filtered_data and not isinstance(filtered_data[key], str)
               for key in text_fields):
            raise ValueError("Campos de texto inválidos")
        if any(key in filtered_data and type(filtered_data[key]) is not bool
               for key in bool_fields):
            raise ValueError("Opções de rede inválidas")
        if 'port' in filtered_data and type(filtered_data['port']) is not int:
            raise ValueError("Porta inválida")
        return cls(**filtered_data)
    
    def to_config_file_content(self) -> str:
        """Generate openfortivpn configuration file content."""
        # This file is parsed by a privileged process. A newline in any field
        # would turn user data into another openfortivpn option.
        values = (self.host, self.username, self.password, self.realm, self.otp,
                  self.trusted_cert, self.user_cert, self.user_key)
        if any(not isinstance(value, str) or '\n' in value or '\r' in value
               for value in values):
            raise ValueError("Os campos do perfil não podem conter quebras de linha")
        if not self.host.strip():
            raise ValueError("Informe o servidor VPN")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("A porta deve estar entre 1 e 65535")

        lines = []
        
        # Host and Port
        lines.append(f"host = {self.host.strip()}")
        if self.port and self.port != 443:
            lines.append(f"port = {self.port}")
            
        # Authentication
        if self.username:
            lines.append(f"username = {self.username}")
        if self.password:
            lines.append(f"password = {self.password}")
        if self.realm:
            lines.append(f"realm = {self.realm}")
        if self.otp:
            lines.append(f"otp = {self.otp}")
            
        # Certificates
        if self.trusted_cert:
            lines.append(f"trusted-cert = {self.trusted_cert}")
        if self.user_cert:
            lines.append(f"user-cert = {self.user_cert}")
        if self.user_key:
            lines.append(f"user-key = {self.user_key}")
            
        # Options
        lines.append(f"set-routes = {1 if self.set_routes else 0}")
        lines.append(f"set-dns = {1 if self.set_dns else 0}")
        lines.append("pppd-use-peerdns = 0")
        
        if self.use_syslog:
            lines.append("use-syslog = 1")
            
        if self.half_internet_routes:
            lines.append("half-internet-routes = 1")
            
        return "\n".join(lines) + "\n"


class ProfileManager:
    """Manages VPN profiles persistence."""
    
    def __init__(self):
        self.config_dir = Path.home() / '.config' / 'openfortivpn-gtk'
        self.profiles_file = self.config_dir / 'profiles.json'
        self._profiles: List[VPNProfile] = []
        self.load_error: Optional[str] = None
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self):
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.config_dir, 0o700)
    
    @property
    def profiles(self) -> List[VPNProfile]:
        """Get all profiles."""
        return self._profiles
    
    def load(self):
        """Load profiles from disk."""
        if self.profiles_file.exists():
            try:
                os.chmod(self.profiles_file, 0o600)
                with open(self.profiles_file, 'r') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("Formato de perfis inválido")
                    self._profiles = [VPNProfile.from_dict(p) for p in data]
                    self.load_error = None
            except (json.JSONDecodeError, IOError, TypeError, ValueError) as e:
                print(f"Error loading profiles: {e}")
                self._profiles = []
                self.load_error = str(e)
        else:
            self._profiles = []
            self.load_error = None
    
    def save(self):
        """Save profiles to disk."""
        if self.load_error:
            raise OSError("O arquivo de perfis existente está inválido; corrija-o antes de salvar")
        temp_name = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix='.profiles-', dir=self.config_dir)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump([p.to_dict() for p in self._profiles], f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_name, self.profiles_file)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)
    
    def add(self, profile: VPNProfile):
        """Add a new profile."""
        self._profiles.append(profile)
        try:
            self.save()
        except OSError:
            self._profiles.pop()
            raise
    
    def update(self, profile: VPNProfile):
        """Update an existing profile."""
        for i, p in enumerate(self._profiles):
            if p.id == profile.id:
                self._profiles[i] = profile
                try:
                    self.save()
                except OSError:
                    self._profiles[i] = p
                    raise
                return
        # If not found, add it
        self.add(profile)
    
    def remove(self, profile_id: str):
        """Remove a profile by ID."""
        previous = self._profiles
        self._profiles = [p for p in self._profiles if p.id != profile_id]
        try:
            self.save()
        except OSError:
            self._profiles = previous
            raise
    
    def get(self, profile_id: str) -> Optional[VPNProfile]:
        """Get a profile by ID."""
        for p in self._profiles:
            if p.id == profile_id:
                return p
        return None
