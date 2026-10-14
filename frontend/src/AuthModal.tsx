import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Form, Input, Modal } from 'antd';

import { DEFAULT_SESSION } from './auth';
import type { AuthSession } from './types';

interface AuthModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: (session: AuthSession) => void;
}

interface AuthFormValues {
  username: string;
  password: string;
}

export function AuthModal({
  open,
  onCancel,
  onSuccess,
}: AuthModalProps) {
  function submit() {
    onSuccess(DEFAULT_SESSION);
  }

  return (
    <Modal
      open={open}
      title={null}
      footer={null}
      width={420}
      onCancel={onCancel}
      destroyOnHidden
      centered
    >
      <div className="auth-modal__header">
        <h2>欢迎来到安心保</h2>
        <p>登录后可使用智能顾问服务</p>
      </div>
      <Form<AuthFormValues>
        layout="vertical"
        initialValues={{ username: 'heima', password: '123456' }}
        onFinish={submit}
        requiredMark={false}
      >
        <Form.Item
          label="用户名"
          name="username"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input prefix={<UserOutlined />} size="large" readOnly />
        </Form.Item>
        <Form.Item
          label="密码"
          name="password"
          rules={[{ required: true, min: 6, message: '密码至少需要 6 位' }]}
        >
          <Input.Password prefix={<LockOutlined />} size="large" readOnly />
        </Form.Item>
        <button className="auth-submit" type="submit">
          登录
        </button>
      </Form>
    </Modal>
  );
}
