import React from 'react'
import { Button, Result } from 'antd'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <Result
          status="error"
          title="页面出现了异常"
          subTitle={this.state.error?.message || '未知错误'}
          extra={
            <Button
              type="primary"
              onClick={() => {
                this.setState({ hasError: false, error: null })
              }}
            >
              重试
            </Button>
          }
        />
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
