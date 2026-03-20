Feature: Probar enviar notificacion Email
  Scenario: Ejecutar exitosamente enviar notificacion Email
    Given que tengo los datos para 'enviar notificacion Email'
    When envío la petición hacia 'enviar notificacion Email'
    Then el código de respuesta para 'enviar notificacion Email' debe ser exitoso